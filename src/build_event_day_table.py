"""Build the Layer 2 source-linked scheduled/news event-day table."""

import argparse

from config import EVENT_DAY_TABLE_FILE, FIRST_RELEASE_OUTCOMES_FILE, NEWS_EVENTS_FILE, RELEASE_CALENDAR_FILE
from event_day_table import build_event_day_table, save_event_day_table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calendar", default=RELEASE_CALENDAR_FILE)
    parser.add_argument("--outcomes", default=FIRST_RELEASE_OUTCOMES_FILE)
    parser.add_argument("--news", default=NEWS_EVENTS_FILE)
    parser.add_argument("--output", default=EVENT_DAY_TABLE_FILE)
    args = parser.parse_args()
    try:
        table = build_event_day_table(args.calendar, args.outcomes, args.news)
        path = save_event_day_table(table, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    overlaps = int(table["overlap_flag"].sum()) if not table.empty else 0
    scheduled = int(table["event_origin"].eq("scheduled").sum()) if not table.empty else 0
    news = int(table["event_origin"].eq("unscheduled").sum()) if not table.empty else 0
    print(f"Wrote {len(table)} events ({scheduled} scheduled, {news} unscheduled) to {path}")
    print(f"Events flagged for grouped/excluded single-event analysis: {overlaps}")
    print("The event table links releases/headlines to source records; run analyze_event_reactions.py to calculate daily gold returns.")


if __name__ == "__main__":
    main()
