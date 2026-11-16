"""Task 2.3.4: event-cluster bootstrap intervals for release vs ordinary days.

Events are resampled with replacement; each drawn event keeps its own release
value and all of its matched ordinary-day values. Descriptive associations only.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from config import (BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, EVENT_UNCERTAINTY_FILE,
                    PRACTICAL_MARGIN_RATIO)
from event_comparison import POOLED_GROUP, QUANTILES, SIZE_MEASURES, _read_inputs


PRIMARY_MEASURE = ("scaled_abs_move", "median")
UNCERTAINTY_COLUMNS = [
    "sample", "group", "measure", "statistic", "release_value", "ordinary_value",
    "ratio", "ratio_ci_low", "ratio_ci_high", "difference", "difference_ci_low",
    "difference_ci_high", "share_resamples_ratio_above_1", "n_events", "n_pairs",
    "resamples", "seed", "primary_test", "verdict",
]


def _clusters(pairs, sessions, measure):
    events = pairs.drop_duplicates("event_id")["event_id"].tolist()
    by_event = pairs.groupby("event_id", sort=False)["control_session_date"].apply(list)
    release_date = pairs.drop_duplicates("event_id").set_index("event_id")["event_session_date"]
    values = sessions[measure]
    release = np.array([values.loc[release_date[e]] for e in events], dtype=float)
    ordinary = [values.loc[by_event[e]].to_numpy(dtype=float) for e in events]
    return release, ordinary


def _stats(release, ordinary):
    out = {}
    for name, q in QUANTILES.items():
        r = float(np.quantile(release, q))
        o = float(np.quantile(ordinary, q))
        out[name] = (r, o)
    return out


def bootstrap_group(pairs, sessions, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED):
    """Return rows of point estimates and percentile intervals for one group."""
    rows = []
    for measure in SIZE_MEASURES:
        release, ordinary = _clusters(pairs, sessions, measure)
        n = len(release)
        point = _stats(release, np.concatenate(ordinary))
        rng = np.random.default_rng(seed)
        draws = {name: [] for name in QUANTILES}
        for _ in range(resamples):
            idx = rng.integers(0, n, size=n)
            sample_stats = _stats(release[idx], np.concatenate([ordinary[i] for i in idx]))
            for name, (r, o) in sample_stats.items():
                draws[name].append((r, o))
        for name, (r, o) in point.items():
            d = np.array(draws[name])
            ratios = np.divide(d[:, 0], d[:, 1], out=np.full(len(d), np.nan), where=d[:, 1] != 0)
            diffs = d[:, 0] - d[:, 1]
            rows.append({
                "measure": measure, "statistic": name,
                "release_value": r, "ordinary_value": o,
                "ratio": r / o if o != 0 else np.nan,
                "ratio_ci_low": float(np.nanquantile(ratios, 0.025)),
                "ratio_ci_high": float(np.nanquantile(ratios, 0.975)),
                "difference": r - o,
                "difference_ci_low": float(np.quantile(diffs, 0.025)),
                "difference_ci_high": float(np.quantile(diffs, 0.975)),
                "share_resamples_ratio_above_1": float(np.nanmean(ratios > 1)),
                "n_events": n, "n_pairs": int(sum(len(x) for x in ordinary)),
                "resamples": resamples, "seed": seed,
            })
    return rows


def verdict(ratio, ci_low, margin=PRACTICAL_MARGIN_RATIO):
    """Pre-declared Layer 2 rule for the primary measure (median scaled move)."""
    if ratio >= margin and ci_low > 1.0:
        return "strong" if ci_low >= margin else "survives"
    return "not_established"


def bootstrap_comparison(matches_path, sessions_path, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED):
    matches, sessions = _read_inputs(matches_path, sessions_path)
    rows = []
    for sample in sorted(matches["sample"].unique(), key=lambda s: (s != "main", s)):
        in_sample = matches[matches["sample"] == sample]
        groups = [(g, in_sample[in_sample["event_type"] == g]) for g in sorted(in_sample["event_type"].unique())]
        groups.append((POOLED_GROUP, in_sample))
        for group, pairs in groups:
            for row in bootstrap_group(pairs, sessions, resamples, seed):
                row.update({"sample": sample, "group": group})
                primary = (row["measure"], row["statistic"]) == PRIMARY_MEASURE
                row["primary_test"] = primary
                row["verdict"] = verdict(row["ratio"], row["ratio_ci_low"]) if primary else ""
                rows.append(row)
    return pd.DataFrame(rows, columns=UNCERTAINTY_COLUMNS)


def save_uncertainty(frame, path=EVENT_UNCERTAINTY_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame[UNCERTAINTY_COLUMNS].copy()
    numeric = ["release_value", "ordinary_value", "ratio", "ratio_ci_low", "ratio_ci_high",
               "difference", "difference_ci_low", "difference_ci_high", "share_resamples_ratio_above_1"]
    output[numeric] = output[numeric].round(6)
    output.to_csv(path, index=False)
    return path
