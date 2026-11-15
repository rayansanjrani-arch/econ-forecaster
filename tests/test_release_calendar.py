import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from release_calendar import CALENDAR_COLUMNS, load_calendar


class ReleaseCalendarTests(unittest.TestCase):
    def test_loads_and_sorts_verified_events(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.csv"
            pd.DataFrame([
                ["2027-02-11", "core_cpi_mom", "CPI", "Jan 2027", "08:30 AM ET", "https://example.test", "now"],
                ["2026-12-10", "core_cpi_mom", "CPI", "Nov 2026", "08:30 AM ET", "https://example.test", "now"],
            ], columns=CALENDAR_COLUMNS).to_csv(path, index=False)
            calendar = load_calendar(path)
            self.assertEqual(calendar["release_date"].tolist(), ["2026-12-10", "2027-02-11"])

    def test_duplicate_release_indicator_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.csv"
            row = ["2026-12-10", "core_cpi_mom", "CPI", "Nov 2026", "08:30 AM ET", "https://example.test", "now"]
            pd.DataFrame([row, row], columns=CALENDAR_COLUMNS).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_calendar(path)


if __name__ == "__main__":
    unittest.main()
