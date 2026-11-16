"""Build Task 2.3.2 matched ordinary comparison days for release events."""

import argparse

import pandas as pd

from config import CONTROLS_PER_EVENT, EVENT_CONTROL_MATCHES_FILE, EVENT_REACTIONS_FILE, GOLD_SESSION_OUTCOMES_FILE, MAIN_SAMPLE_START
from control_matching import match_controls, save_matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reactions", default=EVENT_REACTIONS_FILE)
    parser.add_argument("--sessions", default=GOLD_SESSION_OUTCOMES_FILE)
    parser.add_argument("--output", default=EVENT_CONTROL_MATCHES_FILE)
    args = parser.parse_args()
    try:
        main_matches, main_summary = match_controls(args.reactions, args.sessions, "main", MAIN_SAMPLE_START)
        full_matches, full_summary = match_controls(args.reactions, args.sessions, "full", None)
        matches = pd.concat([main_matches, full_matches], ignore_index=True)
        path = save_matches(matches, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Wrote {len(matches)} event/comparison-day pairs to {path}")
    for summary in (main_summary, full_summary):
        if summary.empty:
            continue
        name = summary["sample"].iloc[0]
        label = f"from {MAIN_SAMPLE_START}" if name == "main" else "secondary check, from first trailing volatility"
        print(f"\n{name} sample ({label}): {len(summary)} events")
        table = summary.groupby("event_type").agg(
            events=("event_id", "size"),
            comparison_days=("n_controls", "sum"),
            events_below_target=("n_controls", lambda s: int((s < CONTROLS_PER_EVENT).sum())),
        )
        print(table.to_string())


if __name__ == "__main__":
    main()
