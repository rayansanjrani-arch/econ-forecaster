"""Parse BLS yearly schedule extracts into release-calendar rows (replication).

Extracts in data/raw/bls/schedule_extracts/YYYY.txt are the CPI, PPI and
Employment Situation lines copied verbatim from https://www.bls.gov/schedule/YYYY/home.htm
(fetched 2026-11-16; a direct download was refused with HTTP 403). Two page
formats exist:
  2005-2007: "The Employment Situation, December 2004 Jan. 7, 2005 8:30 am"
             (the year is often omitted and is inferred from the reference month)
  2008+:     "Friday, January 04, 2008 | 08:30 AM | Employment Situation for December 2007"
"""

import re
from pathlib import Path

import pandas as pd

from release_calendar import CALENDAR_COLUMNS

EXTRACTED_AT_UTC = "2026-11-16T16:45:00+00:00"
SOURCE_URL = "https://www.bls.gov/schedule/{year}/home.htm"
INDICATORS = {
    "employment situation": ("employment_situation", "Employment Situation (payrolls unemployment earnings)"),
    "producer price index": ("ppi", "Producer Price Index"),
    "consumer price index": ("core_cpi_mom", "Consumer Price Index"),
}
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
SHORT_MONTHS = {"jan": 1, "feb": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
                "aug": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
OLD = re.compile(
    r"^(?:The )?(?P<name>Employment Situation|Producer Price Index(?:es)?|Consumer Price Index(?:es)?), "
    r"(?P<ref_month>[A-Za-z]+) (?P<ref_year>\d{4}) (?P<mon>[A-Za-z]+)\.? +(?P<day>\d{1,2})(?:, (?P<year>\d{4}))? "
    r"+(?P<time>\d{1,2}:\d{2}) am$")
NEW = re.compile(
    r"^(?P<weekday>[A-Za-z]+), (?P<month>[A-Za-z]+) (?P<day>\d{2}), (?P<year>\d{4}) \| (?P<time>\d{2}:\d{2}) AM \| "
    r"(?P<name>Employment Situation|Producer Price Index|Consumer Price Index) for (?P<ref_month>[A-Za-z]+) (?P<ref_year>\d{4})$")


def _indicator(name):
    return INDICATORS[re.sub(r"indexes$", "index", name.lower())]


def parse_line(line, page_year):
    line = " ".join(line.split())
    match = NEW.match(line)
    if match:
        date = pd.Timestamp(f"{match['year']}-{MONTHS[match['month'].lower()]:02d}-{int(match['day']):02d}")
        if date.day_name() != match["weekday"]:
            raise ValueError(f"Weekday does not match date in: {line}")
        time = match["time"]
    else:
        match = OLD.match(line)
        if not match:
            raise ValueError(f"Unrecognized schedule line ({page_year}): {line}")
        month = SHORT_MONTHS[match["mon"].lower()]
        ref_month, ref_year = MONTHS[match["ref_month"].lower()], int(match["ref_year"])
        # Releases follow their reference month; a January release covers the prior December.
        year = ref_year if month > ref_month else ref_year + 1
        if match["year"] and int(match["year"]) != year:
            raise ValueError(f"Printed year disagrees with reference period in: {line}")
        date = pd.Timestamp(year=year, month=month, day=int(match["day"]))
        hour, minute = match["time"].split(":")
        time = f"{int(hour):02d}:{minute}"
    indicator, event = _indicator(match["name"])
    ref = f"{match['ref_month'].capitalize()} {match['ref_year']}"
    if time != "08:30":
        raise ValueError(f"Unexpected release time in: {line}")
    return {
        "release_date": date.strftime("%Y-%m-%d"), "indicator": indicator, "event": event,
        "reference_period": ref, "release_time_et": "08:30 AM ET",
        "source_url": SOURCE_URL.format(year=page_year), "checked_at_utc": EXTRACTED_AT_UTC,
    }


def build_calendar(extract_dir, start, end):
    rows = []
    for path in sorted(Path(extract_dir).glob("*.txt")):
        page_year = int(path.stem)
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(parse_line(line, page_year))
    frame = pd.DataFrame(rows, columns=CALENDAR_COLUMNS)
    # A release can appear on two years' pages; keep one, preferring the release year's page.
    frame["_page_matches"] = [d[:4] in u for d, u in zip(frame["release_date"], frame["source_url"])]
    dupes = frame.groupby(["indicator", "reference_period"])["release_date"].nunique()
    conflicts = dupes[dupes > 1]
    if len(conflicts):
        raise ValueError(f"Pages disagree on release dates: {conflicts.index.tolist()}")
    frame = (frame.sort_values(["indicator", "reference_period", "_page_matches"], ascending=[True, True, False])
             .drop_duplicates(["indicator", "reference_period"]).drop(columns="_page_matches"))
    in_window = frame["release_date"].between(start, end)
    frame = frame[in_window].sort_values(["release_date", "indicator"]).reset_index(drop=True)
    return frame[CALENDAR_COLUMNS]


def coverage_problems(frame):
    """Each indicator should have exactly one release per reference month, without gaps."""
    problems = []
    for indicator, part in frame.groupby("indicator"):
        refs = pd.to_datetime(part["reference_period"], format="%B %Y")
        expected = pd.date_range(refs.min(), refs.max(), freq="MS")
        missing = sorted(set(expected) - set(refs))
        if missing:
            problems.append(f"{indicator}: missing reference months {[m.strftime('%Y-%m') for m in missing]}")
        if refs.duplicated().any():
            problems.append(f"{indicator}: duplicate reference months")
    return problems
