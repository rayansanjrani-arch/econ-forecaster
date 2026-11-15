"""Fetch, validate, and archive current-vintage FRED economic series."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from config import (
    FRED_MANIFEST_FILE,
    FRED_SERIES_CATALOG,
    FRED_SNAPSHOT_DIR,
    fred_csv_url,
)


MANIFEST_COLUMNS = [
    "snapshot_id", "series_id", "series_name", "frequency", "units",
    "seasonal_adjustment", "source_agency", "source_url", "snapshot_file",
    "fetched_at_utc", "rows", "missing_values", "missing_observation_dates",
    "first_observation", "last_observation",
]


def validate_fred_frame(frame, series_id):
    """Normalize a FRED CSV and reject invalid dates, values, or frequency gaps."""
    if series_id not in FRED_SERIES_CATALOG:
        raise ValueError(f"Series is not in the configured catalog: {series_id}")
    if frame is None or frame.empty:
        raise ValueError(f"FRED returned no observations for {series_id}")
    required = {"observation_date", series_id}
    if not required.issubset(frame.columns):
        raise ValueError(f"FRED response for {series_id} must contain columns {sorted(required)}")

    result = frame[["observation_date", series_id]].copy()
    dates = pd.to_datetime(result["observation_date"], errors="coerce")
    if dates.isna().any():
        raise ValueError(f"{series_id} contains an invalid observation date")
    if dates.duplicated().any():
        raise ValueError(f"{series_id} contains duplicate observation dates")
    result["observation_date"] = dates.dt.strftime("%Y-%m-%d")
    result = result.sort_values("observation_date", kind="stable").reset_index(drop=True)

    raw_values = result[series_id].replace({".": np.nan, "": np.nan})
    numeric_values = pd.to_numeric(raw_values, errors="coerce")
    invalid = raw_values.notna() & numeric_values.isna()
    if invalid.any():
        raise ValueError(f"{series_id} contains non-numeric values")
    if not np.isfinite(numeric_values.dropna().to_numpy(dtype=float)).all():
        raise ValueError(f"{series_id} contains non-finite values")
    if numeric_values.notna().sum() == 0:
        raise ValueError(f"{series_id} contains no numeric observations")

    date_index = pd.DatetimeIndex(pd.to_datetime(result["observation_date"]))
    frequency = FRED_SERIES_CATALOG[series_id]["frequency"]
    if frequency == "monthly":
        period_index = date_index.to_period("M").asi8
        if (np.diff(period_index) != 1).any() or not (date_index.day == 1).all():
            raise ValueError(f"{series_id} does not match its expected monthly frequency")
    elif frequency == "weekly":
        week_index = date_index.to_period("W-SAT").asi8
        if (np.diff(week_index) != 1).any() or not (date_index.day_of_week == 5).all():
            raise ValueError(f"{series_id} does not match its expected Saturday-weekly frequency")
    elif frequency == "quarterly":
        month_numbers = date_index.month
        period_index = date_index.to_period("M").asi8
        if (
            (np.diff(period_index) != 3).any()
            or not (date_index.day == 1).all()
            or not np.isin(month_numbers, [1, 4, 7, 10]).all()
        ):
            raise ValueError(f"{series_id} does not match its expected quarterly frequency")
    else:
        raise ValueError(f"Unsupported frequency in catalog for {series_id}: {frequency}")
    return result


def _manifest_row(snapshot_id, series_id, frame, fetched_at_utc, snapshot_dir):
    metadata = FRED_SERIES_CATALOG[series_id]
    numeric = pd.to_numeric(
        frame[series_id].replace({".": np.nan, "": np.nan}), errors="coerce"
    )
    observed_dates = frame.loc[numeric.notna(), "observation_date"]
    return {
        "snapshot_id": snapshot_id,
        "series_id": series_id,
        "series_name": metadata["name"],
        "frequency": metadata["frequency"],
        "units": metadata["units"],
        "seasonal_adjustment": metadata["seasonal_adjustment"],
        "source_agency": metadata["source_agency"],
        "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
        "snapshot_file": str((snapshot_dir / f"{series_id}.csv").relative_to(snapshot_dir.parent.parent)),
        "fetched_at_utc": fetched_at_utc,
        "rows": len(frame),
        "missing_values": int(numeric.isna().sum()),
        "missing_observation_dates": ";".join(
            frame.loc[numeric.isna(), "observation_date"].astype(str).tolist()
        ),
        "first_observation": observed_dates.iloc[0],
        "last_observation": observed_dates.iloc[-1],
    }


def _load_manifest(path):
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=MANIFEST_COLUMNS)
    frame = pd.read_csv(path, keep_default_na=False)
    missing = [column for column in MANIFEST_COLUMNS if column not in frame.columns]
    legacy_optional = {"missing_observation_dates"}
    unsupported_missing = [column for column in missing if column not in legacy_optional]
    if unsupported_missing:
        raise ValueError(f"FRED manifest is missing columns: {', '.join(unsupported_missing)}")
    for column in missing:
        frame[column] = ""
    return frame[MANIFEST_COLUMNS]


def fetch_and_archive(series_ids=None, reader=pd.read_csv, snapshot_dir=FRED_SNAPSHOT_DIR,
                      manifest_path=FRED_MANIFEST_FILE, fetched_at_utc=None):
    """Fetch a batch; validate all series before writing one immutable snapshot."""
    series_ids = list(series_ids or FRED_SERIES_CATALOG)
    unknown = [series_id for series_id in series_ids if series_id not in FRED_SERIES_CATALOG]
    if unknown:
        raise ValueError(f"Unknown FRED series: {', '.join(unknown)}")
    if len(set(series_ids)) != len(series_ids):
        raise ValueError("A FRED series was requested more than once")

    fetched_at_utc = fetched_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    fetched_at = pd.to_datetime(fetched_at_utc, utc=True, errors="coerce")
    if pd.isna(fetched_at):
        raise ValueError("fetched_at_utc must be a valid timestamp")
    snapshot_id = fetched_at.strftime("%Y%m%dT%H%M%SZ")

    frames = {}
    for series_id in series_ids:
        raw = reader(fred_csv_url(series_id), dtype=str, keep_default_na=False)
        frames[series_id] = validate_fred_frame(raw, series_id)

    snapshot_root = Path(snapshot_dir)
    manifest_path = Path(manifest_path)
    snapshot_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    final_snapshot = snapshot_root / snapshot_id
    if final_snapshot.exists():
        raise FileExistsError(f"Snapshot already exists: {final_snapshot}")
    stage = snapshot_root / f".{snapshot_id}.tmp"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    try:
        for series_id, frame in frames.items():
            frame.to_csv(stage / f"{series_id}.csv", index=False)
        rows = [
            _manifest_row(snapshot_id, series_id, frame, fetched_at.isoformat(), final_snapshot)
            for series_id, frame in frames.items()
        ]
        stage.rename(final_snapshot)
        previous = _load_manifest(manifest_path)
        updated = pd.concat([previous, pd.DataFrame(rows, columns=MANIFEST_COLUMNS)], ignore_index=True)
        temp_manifest = manifest_path.with_name(manifest_path.name + ".tmp")
        updated.to_csv(temp_manifest, index=False)
        os.replace(temp_manifest, manifest_path)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return snapshot_id, final_snapshot, manifest_path, rows
