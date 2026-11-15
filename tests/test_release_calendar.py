import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from release_calendar import CALENDAR_COLUMNS, enrich_calendar, load_calendar
from config import RELEASE_CALENDAR_FILE


class ReleaseCalendarTests(unittest.TestCase):
    def test_project_calendar_includes_verified_gdp_and_retail_schedule(self):
        calendar = load_calendar(RELEASE_CALENDAR_FILE)
        gdp = calendar[calendar["indicator"].str.startswith("real_gdp_")]
        retail = calendar[calendar["indicator"] == "retail_sales_advance"]

        self.assertEqual(len(gdp), 14)
        self.assertEqual(len(retail), 14)
        self.assertIn("2027-01-28", gdp["release_date"].tolist())
        self.assertIn("2026-11-17", retail["release_date"].tolist())
        self.assertTrue(gdp["source_url"].str.startswith("https://www.bea.gov/").all())
        self.assertTrue(retail["source_url"].str.startswith("https://www.census.gov/").all())

    def test_loads_and_sorts_verified_events(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.csv"
            pd.DataFrame([
                ["2027-02-11", "core_cpi_mom", "CPI", "Jan 2027", "08:30 AM ET", "https://example.test", "2026-11-15T14:00:00+00:00"],
                ["2026-12-10", "core_cpi_mom", "CPI", "Nov 2026", "08:30 AM ET", "https://example.test", "2026-11-15T14:00:00+00:00"],
            ], columns=CALENDAR_COLUMNS).to_csv(path, index=False)
            calendar = load_calendar(path)
            self.assertEqual(calendar["release_date"].tolist(), ["2026-12-10", "2027-02-11"])

    def test_duplicate_release_indicator_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.csv"
            row = ["2026-12-10", "core_cpi_mom", "CPI", "Nov 2026", "08:30 AM ET", "https://example.test", "2026-11-15T14:00:00+00:00"]
            pd.DataFrame([row, row], columns=CALENDAR_COLUMNS).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_calendar(path)

    def test_converts_eastern_to_utc_and_pakistan_with_daylight_saving(self):
        frame = pd.DataFrame([
            ["2026-12-10", "cpi", "CPI", "Nov 2026", "08:30 AM ET", "https://example.test", "2026-11-15T14:00:00+00:00"],
            ["2027-06-10", "ppi", "PPI", "May 2027", "08:30 AM ET", "https://example.test", "2026-11-15T14:00:00+00:00"],
        ], columns=CALENDAR_COLUMNS)
        enriched = enrich_calendar(frame)
        self.assertEqual(enriched.loc[0, "release_time_utc"], "2026-12-10T13:30+00:00")
        self.assertEqual(enriched.loc[0, "release_time_pk"], "2026-12-10 18:30 PKT")
        self.assertEqual(enriched.loc[1, "release_time_utc"], "2027-06-10T12:30+00:00")
        self.assertEqual(enriched.loc[1, "release_time_pk"], "2027-06-10 17:30 PKT")

    def test_flags_same_day_and_near_time_overlaps(self):
        frame = pd.DataFrame([
            ["2026-12-10", "cpi", "CPI", "Nov 2026", "08:30 AM ET", "https://example.test", "2026-11-15T14:00:00+00:00"],
            ["2026-12-10", "claims", "Claims", "Week ending Dec 5", "09:00 AM ET", "https://example.test", "2026-11-15T14:00:00+00:00"],
            ["2026-12-10", "other", "Other release", "Nov 2026", "11:00 AM ET", "https://example.test", "2026-11-15T14:00:00+00:00"],
        ], columns=CALENDAR_COLUMNS)
        enriched = enrich_calendar(frame)
        self.assertEqual(enriched["same_day_event_count"].tolist(), [3, 3, 3])
        self.assertEqual(enriched["events_within_60m"].tolist(), [1, 1, 0])
        self.assertTrue(enriched["overlap_flag"].all())

    def test_invalid_release_time_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.csv"
            row = ["2026-12-10", "core_cpi_mom", "CPI", "Nov 2026", "morning", "https://example.test", "2026-11-15T14:00:00+00:00"]
            pd.DataFrame([row], columns=CALENDAR_COLUMNS).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Invalid release date/time"):
                load_calendar(path)


if __name__ == "__main__":
    unittest.main()
