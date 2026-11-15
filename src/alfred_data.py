"""Fetch and archive one ALFRED point-in-time vintage for configured FRED series."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from config import ALFRED_MANIFEST_FILE, ALFRED_SNAPSHOT_DIR, FRED_SERIES_CATALOG
from economic_data import validate_fred_frame


ALFRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
ALFRED_MANIFEST_COLUMNS = [
    "snapshot_id", "vintage_date", "series_id", "series_name", "frequency",
    "units", "seasonal_adjustment", "source_agency", "source_url",
    "snapshot_file", "fetched_at_utc", "api_realtime_start", "api_realtime_end",
    "rows", "missing_values", "missing_observation_dates", "first_observation",
    "last_observation",
]
API_TIMEOUT_SECONDS = 30


def parse_vintage_date(value):
    """Parse a strict ISO date and reject dates later than today in UTC."""
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Vintage date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != str(value):
        raise ValueError("Vintage date must use YYYY-MM-DD")
    if parsed > datetime.now(timezone.utc).date():
        raise ValueError("Vintage date cannot be in the future")
    return parsed


def _validate_api_key(api_key):
    if not api_key:
        raise ValueError(
            "FRED_API_KEY is not set. Request a key from FRED and set it in this terminal."
        )
    if not re.fullmatch(r"[a-z0-9]{32}", api_key):
        raise ValueError("FRED_API_KEY must be the 32-character key issued by FRED")
    return api_key


def build_alfred_request(series_id, vintage_date, api_key):
    """Build the official Version 1 request; FRED requires api_key in the HTTPS query."""
    if series_id not in FRED_SERIES_CATALOG:
        raise ValueError(f"Series is not in the configured catalog: {series_id}")
    vintage_date = parse_vintage_date(vintage_date)
    api_key = _validate_api_key(api_key)
    query = urlencode({
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "output_type": 1,
        "vintage_dates": vintage_date.isoformat(),
        "limit": 100000,
        "sort_order": "asc",
    })
    return Request(
        f"{ALFRED_API_URL}?{query}",
        headers={"User-Agent": "EconForecaster/1.0"},
    )


def fetch_vintage_frame(series_id, vintage_date, api_key=None, requester=urlopen):
    """Return observations as they stood on an ALFRED vintage date plus API metadata."""
    if series_id not in FRED_SERIES_CATALOG:
        raise ValueError(f"Series is not in the configured catalog: {series_id}")
    vintage_date = parse_vintage_date(vintage_date)
    api_key = _validate_api_key(api_key if api_key is not None else os.environ.get("FRED_API_KEY"))
    request = build_alfred_request(series_id, vintage_date, api_key)
    try:
        with requester(request, timeout=API_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = f"FRED ALFRED API request failed with HTTP {exc.code}"
        if exc.code in (401, 403):
            message += "; check that FRED_API_KEY is valid"
        raise RuntimeError(message) from None
    except URLError as exc:
        raise RuntimeError("Could not reach the FRED ALFRED API; check the network connection") from None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("FRED ALFRED API returned invalid JSON") from exc

    if "error_message" in payload:
        code = payload.get("error_code", "unknown")
        raise RuntimeError(f"FRED ALFRED API error {code}: {payload['error_message']}")
    observations = payload.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError(f"ALFRED returned no observations for {series_id} at {vintage_date}")
    raw = pd.DataFrame(observations)
    if not {"date", "value"}.issubset(raw.columns):
        raise ValueError(f"ALFRED response for {series_id} is missing date/value fields")
    frame = raw.rename(columns={"date": "observation_date", "value": series_id})
    frame = validate_fred_frame(frame, series_id)
    metadata = {
        "api_realtime_start": payload.get("realtime_start", ""),
        "api_realtime_end": payload.get("realtime_end", ""),
    }
    return frame, metadata


def _load_alfred_manifest(path):
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=ALFRED_MANIFEST_COLUMNS)
    frame = pd.read_csv(path, keep_default_na=False)
    if frame.columns.tolist() != ALFRED_MANIFEST_COLUMNS:
        raise ValueError("Existing ALFRED manifest columns do not match the expected schema")
    return frame


def fetch_and_archive_vintage(vintage_date, series_ids=None, api_key=None,
                              requester=urlopen, snapshot_dir=ALFRED_SNAPSHOT_DIR,
                              manifest_path=ALFRED_MANIFEST_FILE, fetched_at_utc=None):
    """Fetch and validate all requested series before archiving a vintage snapshot."""
    vintage_date = parse_vintage_date(vintage_date)
    api_key = _validate_api_key(api_key if api_key is not None else os.environ.get("FRED_API_KEY"))
    series_ids = list(series_ids or FRED_SERIES_CATALOG)
    unknown = [series_id for series_id in series_ids if series_id not in FRED_SERIES_CATALOG]
    if unknown:
        raise ValueError(f"Unknown FRED series: {', '.join(unknown)}")
    if not series_ids:
        raise ValueError("At least one series must be requested")
    if len(set(series_ids)) != len(series_ids):
        raise ValueError("A FRED series was requested more than once")

    fetched_at_utc = fetched_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    fetched_at = pd.to_datetime(fetched_at_utc, utc=True, errors="coerce")
    if pd.isna(fetched_at):
        raise ValueError("fetched_at_utc must be a valid timestamp")
    snapshot_id = f"asof_{vintage_date:%Y%m%d}_{fetched_at.strftime('%Y%m%dT%H%M%SZ')}"

    frames = {}
    response_metadata = {}
    for series_id in series_ids:
        frames[series_id], response_metadata[series_id] = fetch_vintage_frame(
            series_id, vintage_date, api_key=api_key, requester=requester
        )

    snapshot_root = Path(snapshot_dir)
    manifest_path = Path(manifest_path)
    final_snapshot = snapshot_root / vintage_date.isoformat() / snapshot_id
    stage = final_snapshot.with_name(f".{snapshot_id}.tmp")
    if final_snapshot.exists():
        raise FileExistsError(f"ALFRED snapshot already exists: {final_snapshot}")
    snapshot_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    stage.parent.mkdir(parents=True, exist_ok=True)
    stage.mkdir()
    try:
        rows = []
        for series_id, frame in frames.items():
            frame.to_csv(stage / f"{series_id}.csv", index=False)
            metadata = FRED_SERIES_CATALOG[series_id]
            numeric = pd.to_numeric(frame[series_id].replace({".": np.nan, "": np.nan}), errors="coerce")
            observed_dates = frame.loc[numeric.notna(), "observation_date"]
            rows.append({
                "snapshot_id": snapshot_id,
                "vintage_date": vintage_date.isoformat(),
                "series_id": series_id,
                "series_name": metadata["name"],
                "frequency": metadata["frequency"],
                "units": metadata["units"],
                "seasonal_adjustment": metadata["seasonal_adjustment"],
                "source_agency": metadata["source_agency"],
                "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
                "snapshot_file": str((final_snapshot / f"{series_id}.csv").relative_to(manifest_path.parent.parent)),
                "fetched_at_utc": fetched_at.isoformat(),
                **response_metadata[series_id],
                "rows": len(frame),
                "missing_values": int(numeric.isna().sum()),
                "missing_observation_dates": ";".join(
                    frame.loc[numeric.isna(), "observation_date"].astype(str).tolist()
                ),
                "first_observation": observed_dates.iloc[0],
                "last_observation": observed_dates.iloc[-1],
            })
        previous = _load_alfred_manifest(manifest_path)
        updated = pd.concat(
            [previous, pd.DataFrame(rows, columns=ALFRED_MANIFEST_COLUMNS)], ignore_index=True
        )
        temp_manifest = manifest_path.with_name(manifest_path.name + ".tmp")
        updated.to_csv(temp_manifest, index=False)
        stage.rename(final_snapshot)
        try:
            os.replace(temp_manifest, manifest_path)
        except Exception:
            shutil.rmtree(final_snapshot)
            raise
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        temp_manifest = manifest_path.with_name(manifest_path.name + ".tmp")
        if temp_manifest.exists():
            temp_manifest.unlink()
        raise
    return snapshot_id, final_snapshot, manifest_path, rows
