"""Display upcoming, manually verified economic release dates."""

import argparse
from pathlib import Path

import pandas as pd

from config import RELEASE_CALENDAR_FILE


CALENDAR_COLUMNS = [
    "release_date", "indicator", "event", "reference_period",
    "release_time_et", "source_url", "checked_at_utc",
]


def load_calendar(path=RELEASE_CALENDAR_FILE):
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=CALENDAR_COLUMNS)
    frame = pd.read_csv(path, keep_default_na=False)
    missing = [column for column in CALENDAR_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Calendar is missing columns: {', '.join(missing)}")
    frame = frame[CALENDAR_COLUMNS].copy()
    dates = pd.to_datetime(frame["release_date"], errors="coerce")
    if dates.isna().any():
        raise ValueError("Calendar contains an invalid release_date")
    if frame[["indicator", "source_url", "checked_at_utc"]].apply(
        lambda column: column.astype(str).str.strip().eq("")
    ).any().any():
        raise ValueError("Every calendar row needs an indicator, source_url, and checked_at_utc")
    if frame.duplicated(["release_date", "indicator"]).any():
        raise ValueError("Calendar contains duplicate release_date/indicator rows")
    frame["release_date"] = dates.dt.strftime("%Y-%m-%d")
    return frame.sort_values(["release_date", "release_time_et", "indicator"])


def main(path=RELEASE_CALENDAR_FILE, today=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="show past dates too")
    args = parser.parse_args()
    frame = load_calendar(path)
    if frame.empty:
        print(f"No calendar entries. Add verified dates to {path}.")
        return
    if not args.all:
        current_day = pd.Timestamp(today or "today").strftime("%Y-%m-%d")
        frame = frame.loc[frame["release_date"] >= current_day]
    if frame.empty:
        print("No upcoming releases in the calendar.")
        return
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
