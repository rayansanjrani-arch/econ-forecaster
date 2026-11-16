"""Task 2.3.2: match each usable release event to ordinary gold sessions.

Matching rule (declared in EXPERIMENTS.md before results): same weekday, within
a window of observed sessions, excluding release days and sessions adjacent to
them; take the nearest sessions, ties broken by the earlier date. No randomness.
"""

from pathlib import Path

import pandas as pd

from config import (
    CONTROL_EVENT_BUFFER_SESSIONS, CONTROL_WINDOW_SESSIONS, CONTROLS_PER_EVENT,
    EVENT_CONTROL_MATCHES_FILE, MAIN_SAMPLE_START,
)


MATCH_COLUMNS = [
    "sample", "event_id", "event_type", "event_session_date", "event_weekday",
    "control_rank", "control_session_date", "session_distance",
]
USABLE_STATUSES = {"ok", "partial_horizons_at_end_of_gold_history"}


def _is_true(value):
    return str(value).strip().lower() in {"true", "1", "yes"}


def _read_sessions(path):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    for column in ("date", "trailing_vol_pct"):
        if column not in frame.columns:
            raise ValueError(f"Session outcomes are missing column: {column}")
    dates = pd.to_datetime(frame["date"], errors="coerce")
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError("Session outcome dates must be valid and unique")
    if not dates.is_monotonic_increasing:
        raise ValueError("Session outcomes must be sorted by date")
    return frame.assign(_date=dates).reset_index(drop=True)


def _read_reactions(path):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"event_id", "event_type", "single_event_eligible", "analysis_status", "gold_event_session_date"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Event reactions are missing columns: {', '.join(missing)}")
    return frame


def match_controls(
    reactions_path, sessions_path, sample="main", sample_start=MAIN_SAMPLE_START,
    window=CONTROL_WINDOW_SESSIONS, per_event=CONTROLS_PER_EVENT,
    buffer=CONTROL_EVENT_BUFFER_SESSIONS, sample_end=None,
):
    """Return (matches, event_summary) for one sample definition.

    `sample_start` of None means no date restriction beyond trailing-volatility
    availability. Both the event session and its comparison sessions must be in
    the sample.
    """
    sessions = _read_sessions(sessions_path)
    reactions = _read_reactions(reactions_path)
    position = {date: i for i, date in enumerate(sessions["date"])}

    in_sample = sessions["trailing_vol_pct"].ne("")
    if sample_start is not None:
        in_sample &= sessions["_date"] >= pd.Timestamp(sample_start)
    if sample_end is not None:
        in_sample &= sessions["_date"] <= pd.Timestamp(sample_end)

    release_positions = {
        position[d] for d in reactions["gold_event_session_date"] if d in position
    }
    unknown = set(reactions["gold_event_session_date"]) - set(position) - {""}
    if unknown:
        raise ValueError(f"Event sessions missing from session outcomes: {sorted(unknown)[:5]}")
    blocked = {p + k for p in release_positions for k in range(-buffer, buffer + 1)}
    weekdays = sessions["_date"].dt.day_of_week

    events = reactions[
        reactions["single_event_eligible"].map(_is_true)
        & reactions["analysis_status"].isin(USABLE_STATUSES)
        & reactions["gold_event_session_date"].ne("")
    ]
    rows, summary = [], []
    for event in events.sort_values(["gold_event_session_date", "event_id"]).to_dict("records"):
        p = position[event["gold_event_session_date"]]
        if not in_sample.iloc[p]:
            continue
        candidates = [
            q for q in range(max(0, p - window), min(len(sessions), p + window + 1))
            if q != p and q not in blocked and in_sample.iloc[q] and weekdays.iloc[q] == weekdays.iloc[p]
        ]
        chosen = sorted(candidates, key=lambda q: (abs(q - p), q))[:per_event]
        for rank, q in enumerate(chosen, start=1):
            rows.append({
                "sample": sample,
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "event_session_date": event["gold_event_session_date"],
                "event_weekday": sessions["_date"].iloc[p].day_name(),
                "control_rank": rank,
                "control_session_date": sessions["date"].iloc[q],
                "session_distance": q - p,
            })
        summary.append({"sample": sample, "event_id": event["event_id"],
                        "event_type": event["event_type"], "n_controls": len(chosen)})
    return pd.DataFrame(rows, columns=MATCH_COLUMNS), pd.DataFrame(summary, columns=["sample", "event_id", "event_type", "n_controls"])


def save_matches(frame, path=EVENT_CONTROL_MATCHES_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame[MATCH_COLUMNS].to_csv(path, index=False)
    return path
