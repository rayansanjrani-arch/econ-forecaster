"""Recheck the downloaded daily gold file without contacting Yahoo."""

import pandas as pd

from config import GOLD_HISTORY_FILE, GOLD_SPIKE_THRESHOLD
from gold_data import inspect_gold_data


def main():
    if not GOLD_HISTORY_FILE.exists():
        raise SystemExit(f"No gold data found. Run: python src/fetch_gold.py")
    data = pd.read_csv(GOLD_HISTORY_FILE)
    report = inspect_gold_data(data, spike_threshold=GOLD_SPIKE_THRESHOLD)
    if report.errors:
        raise SystemExit("Gold data failed validation: " + "; ".join(report.errors))
    print(f"Rows: {len(data):,}; date range: {data['date'].min()} to {data['date'].max()}")
    print(f"Source: {data['source'].dropna().unique().tolist()}")
    print(f"Download timestamps (UTC): {data['downloaded_at_utc'].dropna().unique().tolist()}")
    print(f"Candidate missing weekdays (including holidays): {len(report.missing_weekdays)}")
    print(f"Unexplained weekday gaps: {len(report.unexpected_weekdays)}")
    for date in report.unexpected_weekdays:
        print(f"  {date}")
    print(f"Large moves above {GOLD_SPIKE_THRESHOLD:.0%}: {len(report.large_moves)}")
    for date, change in report.large_moves:
        print(f"  {date}: {change:+.2%}")


if __name__ == "__main__":
    main()
