"""Calculate descriptive daily gold returns around source-linked events.

Daily Yahoo futures bars support day-level association only. These calculations
do not estimate intraday reactions or causal effects.
"""

from pathlib import Path

import pandas as pd

from config import EVENT_DAY_TABLE_FILE, EVENT_REACTIONS_FILE, GOLD_HISTORY_FILE


REACTION_COLUMNS = [
    "event_id", "event_origin", "event_type", "indicator", "event_name",
    "public_timestamp_utc", "event_date_et", "overlap_flag", "overlap_group_id",
    "overlap_policy", "single_event_eligible", "analysis_status",
    "gold_event_session_date", "gold_session_alignment", "prior_session_date",
    "prior_close", "event_session_close", "event_session_return_pct",
    "event_session_range_pct", "return_1_sessions_pct", "return_3_sessions_pct",
    "return_5_sessions_pct", "gold_ticker", "gold_source",
]
HORIZONS = (1, 3, 5)
# An event is only aligned to a gold bar at most this many calendar days later
# (covers weekends and holidays; prevents events before the gold history from
# being attached to its first bar).
MAX_ALIGNMENT_GAP_DAYS = 5
# Saved floats are rounded so rebuilds on different machines/OSes give identical
# files; 8 decimals is far below any meaningful price or percentage difference.
OUTPUT_DECIMALS = 8
NUMERIC_OUTPUT_COLUMNS = [
    "prior_close", "event_session_close", "event_session_return_pct",
    "event_session_range_pct", "return_1_sessions_pct", "return_3_sessions_pct",
    "return_5_sessions_pct",
]


def _read_event_table(source):
    frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    required = {
        "event_id", "event_origin", "event_type", "indicator", "event_name",
        "public_timestamp_utc", "event_date_et", "overlap_flag",
        "overlap_group_id", "overlap_policy",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Event table is missing columns: {', '.join(missing)}")
    if frame["event_id"].eq("").any() or frame["event_id"].duplicated().any():
        raise ValueError("Event table event_id values must be present and unique")
    dates = pd.to_datetime(frame["event_date_et"], errors="coerce")
    if dates.isna().any():
        raise ValueError("Event table contains an invalid event_date_et")
    return frame


def _read_gold(source):
    frame = pd.read_csv(source)
    required = {"date", "open", "high", "low", "close", "ticker", "source"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Gold history is missing columns: {', '.join(missing)}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for field in ("open", "high", "low", "close"):
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    if frame["date"].isna().any() or frame["date"].duplicated().any():
        raise ValueError("Gold history dates must be valid and unique")
    if frame[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError("Gold history OHLC values must be numeric and present")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Gold history OHLC values must be positive")
    return frame.sort_values("date").reset_index(drop=True)


def calculate_event_reactions(event_table, gold_history):
    """Join events to gold sessions and calculate close-to-close horizons.

    The event session is the first available gold bar dated on or after the
    Eastern event date. Returns use the preceding available bar's close as the
    denominator. Horizons count observed gold sessions, not calendar days.
    Events without a following session remain in the output with a status.
    """
    events = _read_event_table(event_table)
    gold = _read_gold(gold_history)
    session_dates = list(gold["date"])
    rows = []
    for event in events.to_dict("records"):
        event_date = pd.Timestamp(event["event_date_et"]).normalize()
        idx = next((i for i, date in enumerate(session_dates) if date >= event_date), None)
        base = {column: event.get(column, "") for column in REACTION_COLUMNS}
        base["single_event_eligible"] = (
            str(event["overlap_flag"]).strip().lower() not in {"true", "1", "yes"}
            and event["overlap_policy"] == "eligible_for_single_event_analysis"
        )
        if idx is None:
            base["analysis_status"] = "no_gold_session_on_or_after_event_date"
            rows.append(base)
            continue
        if (session_dates[idx] - event_date).days > MAX_ALIGNMENT_GAP_DAYS:
            base["analysis_status"] = "no_gold_session_near_event_date"
            rows.append(base)
            continue
        event_bar = gold.iloc[idx]
        base["gold_event_session_date"] = event_bar["date"].strftime("%Y-%m-%d")
        base["gold_session_alignment"] = (
            "same_date" if event_bar["date"] == event_date else "next_available_session"
        )
        base["gold_ticker"] = event_bar["ticker"]
        base["gold_source"] = event_bar["source"]
        if idx == 0:
            base["analysis_status"] = "missing_prior_gold_session"
            rows.append(base)
            continue
        prior = gold.iloc[idx - 1]
        prior_close = float(prior["close"])
        base["prior_session_date"] = prior["date"].strftime("%Y-%m-%d")
        base["prior_close"] = prior_close
        base["event_session_close"] = float(event_bar["close"])
        base["event_session_return_pct"] = (float(event_bar["close"]) / prior_close - 1) * 100
        base["event_session_range_pct"] = (float(event_bar["high"]) - float(event_bar["low"])) / prior_close * 100
        for horizon in HORIZONS:
            target = idx + horizon
            if target < len(gold):
                base[f"return_{horizon}_sessions_pct"] = (
                    float(gold.iloc[target]["close"]) / prior_close - 1
                ) * 100
        base["analysis_status"] = (
            "ok" if all(idx + h < len(gold) for h in HORIZONS)
            else "partial_horizons_at_end_of_gold_history"
        )
        rows.append(base)
    result = pd.DataFrame(rows, columns=REACTION_COLUMNS)
    if not result.empty:
        result = result.sort_values(["event_date_et", "event_id"], kind="stable").reset_index(drop=True)
    return result


def save_event_reactions(frame, path=EVENT_REACTIONS_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame[REACTION_COLUMNS].copy()
    for column in NUMERIC_OUTPUT_COLUMNS:
        values = pd.to_numeric(output[column], errors="coerce").round(OUTPUT_DECIMALS)
        output[column] = values.astype(object).where(values.notna(), "")
    output.to_csv(path, index=False)
    return path
