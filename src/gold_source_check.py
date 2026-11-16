"""Task 1.1a: compare the primary gold series with an independent cross-check.

Returns are calculated only on dates present in both sources, so each pair of
returns covers the same period. Closing times differ (futures vs NYSE close),
so some daily disagreement is expected; differences are flagged, not removed.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from config import GOLD_SOURCE_DIFF_FLAG_PCT, MAIN_SAMPLE_START


CHECK_COLUMNS = [
    "date", "primary_close", "secondary_close", "primary_return_pct",
    "secondary_return_pct", "return_difference_pct", "primary_return_5_pct",
    "secondary_return_5_pct", "flag_large_difference",
]


def _read(path, label):
    frame = pd.read_csv(path, dtype={"date": str})
    for column in ("date", "close"):
        if column not in frame.columns:
            raise ValueError(f"{label} gold file is missing column: {column}")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    if frame["date"].duplicated().any() or frame["close"].isna().any() or (frame["close"] <= 0).any():
        raise ValueError(f"{label} gold file needs unique dates and positive closes")
    ticker = str(frame["ticker"].iloc[0]) if "ticker" in frame.columns and len(frame) else label
    return frame.set_index("date")["close"], ticker


def compare_gold_sources(primary_path, secondary_path, flag_pct=GOLD_SOURCE_DIFF_FLAG_PCT):
    """Return (daily, by_period, coverage) comparison tables."""
    primary, primary_ticker = _read(primary_path, "Primary")
    secondary, secondary_ticker = _read(secondary_path, "Secondary")
    common = sorted(set(primary.index) & set(secondary.index))
    if len(common) < 7:
        raise ValueError("Too few common dates to compare the gold sources")
    daily = pd.DataFrame({
        "date": common,
        "primary_close": primary.loc[common].to_numpy(),
        "secondary_close": secondary.loc[common].to_numpy(),
    })
    for side in ("primary", "secondary"):
        close = daily[f"{side}_close"]
        daily[f"{side}_return_pct"] = (close / close.shift(1) - 1) * 100
        daily[f"{side}_return_5_pct"] = (close / close.shift(5) - 1) * 100
    daily["return_difference_pct"] = daily["secondary_return_pct"] - daily["primary_return_pct"]
    daily["flag_large_difference"] = daily["return_difference_pct"].abs() > flag_pct
    daily = daily[CHECK_COLUMNS]

    dates = pd.to_datetime(daily["date"])
    periods = dates.dt.year.astype(str).rename("period")
    main = daily[dates >= pd.Timestamp(MAIN_SAMPLE_START)]
    early = daily[dates < pd.Timestamp(MAIN_SAMPLE_START)]
    rows = []
    for name, part in daily.groupby(periods):
        rows.append(_period_row(name, part))
    rows.append(_period_row(f"before {MAIN_SAMPLE_START}", early))
    rows.append(_period_row(f"from {MAIN_SAMPLE_START}", main))
    rows.append(_period_row("all", daily))
    by_period = pd.DataFrame(rows)

    coverage = {
        "primary_ticker": primary_ticker, "secondary_ticker": secondary_ticker,
        "primary_rows": len(primary), "secondary_rows": len(secondary), "common_dates": len(common),
        "only_primary": sorted(set(primary.index) - set(secondary.index)),
        "only_secondary": sorted(set(secondary.index) - set(primary.index)),
    }
    return daily, by_period, coverage


def _period_row(name, part):
    valid = part.dropna(subset=["primary_return_pct", "secondary_return_pct"])
    valid5 = part.dropna(subset=["primary_return_5_pct", "secondary_return_5_pct"])

    def corr(a, b):
        return float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 and a.std() > 0 and b.std() > 0 else float("nan")

    return {
        "period": name, "days": len(valid),
        "corr_daily": corr(valid["primary_return_pct"], valid["secondary_return_pct"]),
        "corr_5_session": corr(valid5["primary_return_5_pct"], valid5["secondary_return_5_pct"]),
        "median_abs_difference_pct": float(valid["return_difference_pct"].abs().median()) if len(valid) else float("nan"),
        "flagged_days": int(valid["flag_large_difference"].sum()),
    }


def save_check(daily, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output = daily.copy()
    for column in CHECK_COLUMNS[1:-1]:
        output[column] = output[column].round(6)
    output.to_csv(path, index=False)
    return path
