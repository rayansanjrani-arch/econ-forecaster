"""Task 2.3.1: daily gold move measures, calculated identically for every session.

Event days and ordinary comparison days are later selected from this one table,
so both groups always use the same definitions. Daily futures bars support
day-level description only; they do not identify intraday or causal effects.
"""

from pathlib import Path

import pandas as pd

from config import (
    GOLD_SESSION_OUTCOMES_FILE, GOLD_SPIKE_THRESHOLD, GOLD_THIN_VOLUME_THRESHOLD,
    GOLD_TRAILING_VOL_WINDOW,
)
from event_reactions import _read_gold


OUTCOME_COLUMNS = [
    "date", "prior_session_date", "prior_close", "close",
    "signed_return_pct", "abs_return_pct", "range_pct",
    "trailing_vol_pct", "scaled_abs_move", "trailing_vol_window",
    "insufficient_history", "large_move_flag", "volume", "thin_volume_flag",
    "flat_bar_flag", "gold_ticker", "gold_source",
]
NUMERIC_COLUMNS = [
    "prior_close", "close", "signed_return_pct", "abs_return_pct",
    "range_pct", "trailing_vol_pct", "scaled_abs_move",
]
OUTPUT_DECIMALS = 8


def calculate_session_outcomes(gold_history, window=GOLD_TRAILING_VOL_WINDOW):
    """Return one row per gold session with move and trailing-volatility measures.

    Trailing volatility at session t is the sample standard deviation of the
    `window` returns ending at session t-1, so it never uses session t itself.
    The first session has no prior close and therefore no return.
    """
    if int(window) < 2:
        raise ValueError("Trailing volatility window must be at least 2 sessions")
    gold = _read_gold(gold_history)
    out = pd.DataFrame({"date": gold["date"].dt.strftime("%Y-%m-%d")})
    prior_close = gold["close"].shift(1)
    out["prior_session_date"] = out["date"].shift(1)
    out["prior_close"] = prior_close
    out["close"] = gold["close"]
    out["signed_return_pct"] = (gold["close"] / prior_close - 1) * 100
    out["abs_return_pct"] = out["signed_return_pct"].abs()
    out["range_pct"] = (gold["high"] - gold["low"]) / prior_close * 100
    trailing = out["signed_return_pct"].shift(1).rolling(window, min_periods=window).std(ddof=1)
    out["trailing_vol_pct"] = trailing
    out["scaled_abs_move"] = out["abs_return_pct"] / trailing.where(trailing > 0)
    out["trailing_vol_window"] = int(window)
    out["insufficient_history"] = trailing.isna()
    out["large_move_flag"] = out["abs_return_pct"] > GOLD_SPIKE_THRESHOLD * 100
    # Review flags only. Jan 2019-May 2020 Yahoo GC=F bars show very low volume and
    # flat OHLC bars, so ranges there may not reflect the active contract.
    if "volume" in gold.columns:
        volume = pd.to_numeric(gold["volume"], errors="coerce")
        out["volume"] = volume
        out["thin_volume_flag"] = (volume < GOLD_THIN_VOLUME_THRESHOLD).astype(object).where(volume.notna(), "")
    else:
        out["volume"] = ""
        out["thin_volume_flag"] = ""
    out["flat_bar_flag"] = gold["high"].eq(gold["low"])
    out["gold_ticker"] = gold["ticker"]
    out["gold_source"] = gold["source"]
    return out[OUTCOME_COLUMNS]


def save_session_outcomes(frame, path=GOLD_SESSION_OUTCOMES_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame[OUTCOME_COLUMNS].copy()
    for column in NUMERIC_COLUMNS:
        values = pd.to_numeric(output[column], errors="coerce").round(OUTPUT_DECIMALS)
        output[column] = values.astype(object).where(values.notna(), "")
    output["prior_session_date"] = output["prior_session_date"].fillna("")
    output.to_csv(path, index=False)
    return path
