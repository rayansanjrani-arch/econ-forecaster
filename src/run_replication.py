"""Run the declared 2005-2018 replication of Task 2.3 on GLD with unchanged rules.

Rules were declared in EXPERIMENTS.md before any pre-2019 data was collected.
Outputs go to reports/replication_2005_2018/; primary 2019+ outputs are untouched.
"""

import pandas as pd

from config import (FIRST_RELEASE_OUTCOMES_FILE, GOLD_GLD_LONG_FILE, NEWS_EVENTS_FILE,
                    REPLICATION_CALENDAR_FILE, REPLICATION_DIR, REPLICATION_END, REPLICATION_START)
from control_matching import match_controls, save_matches
from event_comparison import compare_release_and_ordinary_days, save_comparison
from event_day_table import build_event_day_table, save_event_day_table
from event_reactions import calculate_event_reactions, save_event_reactions
from event_uncertainty import bootstrap_comparison, save_uncertainty
from session_outcomes import calculate_session_outcomes, save_session_outcomes

SAMPLES = [
    ("replication", REPLICATION_START, REPLICATION_END),
    ("rep_2005_2011", REPLICATION_START, "2011-12-31"),
    ("rep_2012_2018", "2012-01-01", REPLICATION_END),
]
VERDICT_LABEL = {"survives": "replicated", "strong": "replicated (strong)", "not_established": "not replicated"}


def main():
    out = REPLICATION_DIR
    out.mkdir(parents=True, exist_ok=True)
    table = build_event_day_table(REPLICATION_CALENDAR_FILE, FIRST_RELEASE_OUTCOMES_FILE, NEWS_EVENTS_FILE)
    table = table[table["event_origin"] == "scheduled"]
    events_path = save_event_day_table(table, out / "event_day_table.csv")
    reactions = calculate_event_reactions(events_path, GOLD_GLD_LONG_FILE)
    reactions_path = save_event_reactions(reactions, out / "event_reactions.csv")
    sessions = calculate_session_outcomes(GOLD_GLD_LONG_FILE)
    sessions_path = save_session_outcomes(sessions, out / "gold_session_outcomes.csv")
    print(f"Events: {len(table)} (overlap-flagged {int(table['overlap_flag'].sum())}); "
          f"reaction statuses: {reactions['analysis_status'].value_counts().to_dict()}")

    matches = []
    for name, start, end in SAMPLES:
        m, summary = match_controls(reactions_path, sessions_path, name, start, sample_end=end)
        matches.append(m)
        print(f"{name}: {len(summary)} events, {len(m)} pairs, events below 5 matches: "
              f"{int((summary['n_controls'] < 5).sum())}")
    matches_path = save_matches(pd.concat(matches, ignore_index=True), out / "event_control_matches.csv")

    summary = compare_release_and_ordinary_days(matches_path, sessions_path)
    save_comparison(summary, out / "event_vs_ordinary_summary.csv")
    uncertainty = bootstrap_comparison(matches_path, sessions_path)
    save_uncertainty(uncertainty, out / "event_vs_ordinary_uncertainty.csv")

    primary = uncertainty[uncertainty["primary_test"]].copy()
    primary["replication_verdict"] = primary["verdict"].map(VERDICT_LABEL)
    print("\nPrimary test: median scaled move, release / ordinary, 95% event-bootstrap interval")
    print(primary[["sample", "group", "ratio", "ratio_ci_low", "ratio_ci_high",
                   "share_resamples_ratio_above_1", "n_events", "replication_verdict"]].round(3).to_string(index=False))
    es = uncertainty[(uncertainty["group"] == "employment_situation") & (uncertainty["measure"] == "scaled_abs_move")
                     & uncertainty["statistic"].isin(["p75", "p90"])]
    print("\nSecondary (suggestive): Employment Situation upper-percentile scaled-move ratios")
    print(es[["sample", "statistic", "ratio", "ratio_ci_low", "ratio_ci_high", "n_events"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
