"""Build the 2005-2018 CPI/PPI/Employment Situation calendar for the replication test."""

from bls_schedule_extracts import build_calendar, coverage_problems
from config import BLS_SCHEDULE_EXTRACT_DIR, REPLICATION_CALENDAR_FILE, REPLICATION_END, REPLICATION_START


def main():
    calendar = build_calendar(BLS_SCHEDULE_EXTRACT_DIR, REPLICATION_START, REPLICATION_END)
    problems = coverage_problems(calendar)
    if problems:
        raise SystemExit("Calendar coverage problems: " + "; ".join(problems))
    REPLICATION_CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    calendar.to_csv(REPLICATION_CALENDAR_FILE, index=False)
    print(f"Wrote {len(calendar)} releases to {REPLICATION_CALENDAR_FILE}")
    print(calendar["indicator"].value_counts().to_string())


if __name__ == "__main__":
    main()
