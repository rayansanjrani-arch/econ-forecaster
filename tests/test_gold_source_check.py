import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gold_data import drop_incomplete_sessions, inspect_gold_data
from gold_source_check import CHECK_COLUMNS, compare_gold_sources


class GoldSourceCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.primary = root / "gc.csv"
        self.secondary = root / "gld.csv"
        dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2020-05-25", periods=12)]
        self.dates = dates
        closes = [100, 101, 102, 101, 103, 104, 103, 105, 106, 104, 107, 108]
        pd.DataFrame({"date": dates, "close": closes, "ticker": "GC=F"}).to_csv(self.primary, index=False)
        # GLD = one-tenth of the price, one date missing, one extra date, one disagreement
        gld = pd.DataFrame({"date": dates, "close": [c / 10 for c in closes], "ticker": "GLD"})
        gld.loc[gld.date == dates[6], "close"] = 10.6  # +2.9% vs primary -1.0%
        gld = gld[gld.date != dates[3]]
        gld = pd.concat([gld, pd.DataFrame([{"date": "2020-06-13", "close": 10.8, "ticker": "GLD"}])])
        gld.to_csv(self.secondary, index=False)

    def tearDown(self):
        self.temp.cleanup()

    def test_returns_use_common_dates_and_flag_disagreements(self):
        daily, by_period, coverage = compare_gold_sources(self.primary, self.secondary, flag_pct=1.5)
        self.assertEqual(daily.columns.tolist(), CHECK_COLUMNS)
        self.assertEqual(coverage["only_primary"], [self.dates[3]])
        self.assertEqual(coverage["only_secondary"], ["2020-06-13"])
        # dates[4] return spans dates[2] -> dates[4] in both sources (dates[3] is not common)
        row = daily.set_index("date").loc[self.dates[4]]
        self.assertAlmostEqual(row.primary_return_pct, (103 / 102 - 1) * 100)
        self.assertAlmostEqual(row.secondary_return_pct, (103 / 102 - 1) * 100)
        flagged = daily[daily.flag_large_difference].date.tolist()
        self.assertEqual(flagged, [self.dates[6], self.dates[7]])  # disagreement and its reversal

    def test_period_summary_splits_main_sample(self):
        _, by_period, _ = compare_gold_sources(self.primary, self.secondary)
        periods = by_period.period.tolist()
        self.assertIn("before 2020-06-01", periods)
        self.assertIn("from 2020-06-01", periods)
        self.assertEqual(by_period.set_index("period").loc["all", "flagged_days"], 2)

    def test_identical_series_agree_perfectly(self):
        _, by_period, _ = compare_gold_sources(self.primary, self.primary)
        row = by_period.set_index("period").loc["all"]
        self.assertAlmostEqual(row.corr_daily, 1.0)
        self.assertEqual(row.flagged_days, 0)
        self.assertAlmostEqual(row.median_abs_difference_pct, 0.0)

    def test_rejects_duplicate_dates(self):
        frame = pd.read_csv(self.secondary)
        pd.concat([frame, frame.iloc[[0]]]).to_csv(self.secondary, index=False)
        with self.assertRaisesRegex(ValueError, "unique dates"):
            compare_gold_sources(self.primary, self.secondary)


class ExtraClosureTests(unittest.TestCase):
    def test_declared_extra_closure_is_not_an_unexplained_gap(self):
        dates = ["2025-01-07", "2025-01-08", "2025-01-10"]  # 2025-01-09 missing
        frame = pd.DataFrame({"date": dates, "open": [1, 1, 1], "high": [2, 2, 2], "low": [1, 1, 1], "close": [1.5] * 3})
        self.assertEqual(inspect_gold_data(frame).unexpected_weekdays, ["2025-01-09"])
        report = inspect_gold_data(frame, extra_closures=("2025-01-09",))
        self.assertEqual(report.unexpected_weekdays, [])
        self.assertTrue(report.valid)


class IncompleteSessionTests(unittest.TestCase):
    def test_drops_bars_dated_today_or_later_in_new_york(self):
        frame = pd.DataFrame({"date": ["2026-11-13", "2026-11-16"], "close": [355.45, 353.59]})
        kept, dropped = drop_incomplete_sessions(frame, "2026-11-16")
        self.assertEqual(kept["date"].tolist(), ["2026-11-13"])
        self.assertEqual(dropped, ["2026-11-16"])
        kept, dropped = drop_incomplete_sessions(frame, "2026-11-17")
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])


if __name__ == "__main__":
    unittest.main()
