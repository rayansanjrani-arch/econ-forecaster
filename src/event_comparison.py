"""Task 2.3.3: describe release-day versus matched ordinary-day gold moves.

Descriptive only. Uncertainty intervals are added in Task 2.3.4; daily bars do
not identify intraday or causal effects.
"""

from pathlib import Path

import pandas as pd

from config import EVENT_COMPARISON_FILE


SIZE_MEASURES = ["abs_return_pct", "range_pct", "scaled_abs_move"]
QUANTILES = {"median": 0.5, "p75": 0.75, "p90": 0.9}
SUMMARY_COLUMNS = [
    "sample", "group", "measure", "statistic", "release_value", "ordinary_value",
    "difference", "ratio", "n_events", "n_pairs", "n_unique_ordinary_days",
]
POOLED_GROUP = "all_three"


def _read_inputs(matches_path, sessions_path):
    matches = pd.read_csv(matches_path, dtype={"event_session_date": str, "control_session_date": str})
    required = {"sample", "event_id", "event_type", "event_session_date", "control_session_date"}
    missing = sorted(required.difference(matches.columns))
    if missing:
        raise ValueError(f"Matches are missing columns: {', '.join(missing)}")
    sessions = pd.read_csv(sessions_path, dtype={"date": str})
    needed = ["date", "signed_return_pct"] + SIZE_MEASURES
    missing = sorted(set(needed).difference(sessions.columns))
    if missing:
        raise ValueError(f"Session outcomes are missing columns: {', '.join(missing)}")
    sessions = sessions[needed].set_index("date")
    unknown = (set(matches["event_session_date"]) | set(matches["control_session_date"])) - set(sessions.index)
    if unknown:
        raise ValueError(f"Matched sessions missing from session outcomes: {sorted(unknown)[:5]}")
    return matches, sessions


def _row(sample, group, measure, statistic, release, ordinary, counts):
    # Ratios are only meaningful for size measures; signed returns can be near zero or negative.
    ratio = (release / ordinary if measure in SIZE_MEASURES and pd.notna(ordinary) and ordinary != 0
             else float("nan"))
    return {
        "sample": sample, "group": group, "measure": measure, "statistic": statistic,
        "release_value": release, "ordinary_value": ordinary,
        "difference": release - ordinary, "ratio": ratio, **counts,
    }


def _summarise(sample, group, pairs, sessions):
    events = pairs.drop_duplicates("event_id")
    release = sessions.loc[events["event_session_date"]]
    ordinary = sessions.loc[pairs["control_session_date"]]
    if release[SIZE_MEASURES + ["signed_return_pct"]].isna().any().any() or ordinary.isna().any().any():
        raise ValueError(f"Missing outcome values in {sample}/{group}; check trailing volatility coverage")
    counts = {
        "n_events": len(events), "n_pairs": len(pairs),
        "n_unique_ordinary_days": pairs["control_session_date"].nunique(),
    }
    rows = []
    for measure in SIZE_MEASURES:
        for name, q in QUANTILES.items():
            rows.append(_row(sample, group, measure, name,
                             release[measure].quantile(q), ordinary[measure].quantile(q), counts))
    rows.append(_row(sample, group, "signed_return_pct", "median",
                     release["signed_return_pct"].median(), ordinary["signed_return_pct"].median(), counts))
    rows.append(_row(sample, group, "signed_return_pct", "share_positive",
                     (release["signed_return_pct"] > 0).mean(), (ordinary["signed_return_pct"] > 0).mean(), counts))
    return rows


def compare_release_and_ordinary_days(matches_path, sessions_path):
    matches, sessions = _read_inputs(matches_path, sessions_path)
    rows = []
    for sample in sorted(matches["sample"].unique(), key=lambda s: (s != "main", s)):
        in_sample = matches[matches["sample"] == sample]
        for group in sorted(in_sample["event_type"].unique()):
            rows += _summarise(sample, group, in_sample[in_sample["event_type"] == group], sessions)
        rows += _summarise(sample, POOLED_GROUP, in_sample, sessions)
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def save_comparison(frame, path=EVENT_COMPARISON_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame[SUMMARY_COLUMNS].copy()
    for column in ("release_value", "ordinary_value", "difference", "ratio"):
        output[column] = output[column].round(6)
    output.to_csv(path, index=False)
    return path
