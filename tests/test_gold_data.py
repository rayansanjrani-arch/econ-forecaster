import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gold_data import inspect_gold_data, normalize_yahoo_gold


def bars(dates, closes):
    return pd.DataFrame({
        "date": dates,
        "open": [close - 0.2 for close in closes],
        "high": [close + 0.5 for close in closes],
        "low": [close - 0.5 for close in closes],
        "close": closes,
    })


class GoldDataTests(unittest.TestCase):
    def test_normalizes_yfinance_multiindex_and_adds_provenance(self):
        index = pd.to_datetime(["2026-01-02"])
        columns = pd.MultiIndex.from_tuples([
            ("Open", "GC=F"), ("High", "GC=F"), ("Low", "GC=F"),
            ("Close", "GC=F"), ("Volume", "GC=F"),
        ])
        downloaded = pd.DataFrame([[100, 101, 99, 100.5, 1234]], index=index, columns=columns)
        result = normalize_yahoo_gold(downloaded, "GC=F", "Yahoo", "2026-01-03T00:00:00+00:00")
        self.assertEqual(result.loc[0, "date"], "2026-01-02")
        self.assertEqual(result.loc[0, "close"], 100.5)
        self.assertEqual(result.loc[0, "ticker"], "GC=F")
        self.assertEqual(result.loc[0, "source"], "Yahoo")

    def test_weekend_is_not_reported_as_a_missing_weekday(self):
        report = inspect_gold_data(bars(["2026-01-02", "2026-01-05"], [100, 100.5]))
        self.assertTrue(report.valid)
        self.assertEqual(report.missing_weekdays, [])

    def test_reports_missing_weekdays_without_treating_them_as_hard_errors(self):
        report = inspect_gold_data(bars(["2026-01-05", "2026-01-07"], [100, 100.1]))
        self.assertFalse(report.valid)
        self.assertEqual(report.missing_weekdays, ["2026-01-06"])
        self.assertEqual(report.unexpected_weekdays, ["2026-01-06"])

    def test_reports_large_moves_for_manual_review(self):
        report = inspect_gold_data(bars(["2026-01-05", "2026-01-06"], [100, 106]))
        self.assertEqual(len(report.large_moves), 1)
        self.assertEqual(report.large_moves[0][0], "2026-01-06")
        self.assertAlmostEqual(report.large_moves[0][1], 0.06)

    def test_rejects_inconsistent_ohlc(self):
        data = bars(["2026-01-05"], [100])
        data.loc[0, "low"] = 101
        report = inspect_gold_data(data)
        self.assertFalse(report.valid)
        self.assertTrue(any("Invalid OHLC" in error for error in report.errors))


if __name__ == "__main__":
    unittest.main()
