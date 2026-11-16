"""Build daily gold reaction metrics for the Layer 2 event table."""

import argparse

from config import EVENT_DAY_TABLE_FILE, EVENT_REACTIONS_FILE, GOLD_HISTORY_FILE
from event_reactions import calculate_event_reactions, save_event_reactions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", default=EVENT_DAY_TABLE_FILE)
    parser.add_argument("--gold", default=GOLD_HISTORY_FILE)
    parser.add_argument("--output", default=EVENT_REACTIONS_FILE)
    args = parser.parse_args()
    try:
        reactions = calculate_event_reactions(args.events, args.gold)
        path = save_event_reactions(reactions, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    eligible = int(reactions["single_event_eligible"].sum()) if not reactions.empty else 0
    usable = int(reactions["analysis_status"].isin(["ok", "partial_horizons_at_end_of_gold_history"]).sum()) if not reactions.empty else 0
    print(f"Wrote {len(reactions)} event reaction rows ({usable} with at least an event-session return) to {path}")
    print(f"Single-event eligible rows: {eligible}; usable rows: {usable}")
    print("Returns are descriptive close-to-close daily associations; they do not identify intraday or causal effects.")
    if len(reactions) and not reactions["single_event_eligible"].any():
        print("No non-overlapping events are eligible for single-event analysis.")


if __name__ == "__main__":
    main()
