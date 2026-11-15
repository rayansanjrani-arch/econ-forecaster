"""Display upcoming, manually verified economic release dates."""

import argparse
from datetime import date
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from config import RELEASE_CALENDAR_FILE


CALENDAR_COLUMNS = [
    "release_date", "indicator", "event", "reference_period",
    "release_time_et", "source_url", "checked_at_utc",
]
EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
PAKISTAN = ZoneInfo("Asia/Karachi")
OVERLAP_WINDOW_MINUTES = 60


def _release_datetime(release_date, release_time_et):
    try:
        day = datetime.strptime(str(release_date), "%Y-%m-%d").date()
        time_text = str(release_time_et).removesuffix(" ET").strip()
        release_time = datetime.strptime(time_text, "%I:%M %p").time()
    except ValueError as exc:
        raise ValueError(
            f"Invalid release date/time: {release_date!r} {release_time_et!r}; "
            "expected YYYY-MM-DD and HH:MM AM/PM ET"
        ) from exc
    local = datetime.combine(day, release_time, tzinfo=EASTERN)
    utc = local.astimezone(UTC)
    if utc.astimezone(EASTERN).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError(f"Nonexistent Eastern local time: {release_date} {release_time_et}")
    return local


def enrich_calendar(frame, overlap_window_minutes=OVERLAP_WINDOW_MINUTES):
    """Add timezone conversions and same-day/near-time overlap flags."""
    frame = frame.copy()
    local_times = [
        _release_datetime(day, time)
        for day, time in zip(frame["release_date"], frame["release_time_et"])
    ]
    utc_times = [value.astimezone(UTC) for value in local_times]
    frame["release_time_utc"] = [value.isoformat(timespec="minutes") for value in utc_times]
    frame["release_time_pk"] = [
        value.astimezone(PAKISTAN).strftime("%Y-%m-%d %H:%M PKT") for value in local_times
    ]
    day_counts = frame["release_date"].value_counts()
    frame["same_day_event_count"] = frame["release_date"].map(day_counts).astype(int)
    nearby_counts = []
    for index, timestamp in enumerate(utc_times):
        nearby_counts.append(sum(
            abs((timestamp - other).total_seconds()) <= overlap_window_minutes * 60
            for other_index, other in enumerate(utc_times)
            if other_index != index
        ))
    frame["events_within_60m"] = nearby_counts
    frame["overlap_flag"] = (frame["same_day_event_count"] > 1) | (frame["events_within_60m"] > 0)
    return frame


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
    if frame["checked_at_utc"].map(
        lambda value: pd.isna(pd.to_datetime(value, utc=True, errors="coerce"))
    ).any():
        raise ValueError("Calendar contains an invalid checked_at_utc timestamp")
    frame = enrich_calendar(frame)
    return frame.sort_values(["release_date", "release_time_et", "indicator"])


def main(path=RELEASE_CALENDAR_FILE, today=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="show the complete calendar")
    parser.add_argument("--days", type=int, default=90,
                        help="days ahead to show (default: 90; ignored with --all)")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be at least 1")
    frame = load_calendar(path)
    if frame.empty:
        print(f"No calendar entries. Add verified dates to {path}.")
        return
    if not args.all:
        current_day = pd.Timestamp(today or date.today()).normalize()
        release_days = pd.to_datetime(frame["release_date"])
        frame = frame.loc[
            (release_days >= current_day)
            & (release_days <= current_day + pd.Timedelta(days=args.days))
        ]
    if frame.empty:
        print("No upcoming releases in the calendar.")
        return
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
