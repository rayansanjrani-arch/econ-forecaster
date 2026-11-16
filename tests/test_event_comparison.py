import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from event_comparison import SUMMARY_COLUMNS, compare_release_and_ordinary_days, save_comparison


class EventComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.sessions_path = root / "sessions.csv"
        self.matches_path = root / "matches.csv"
        signed = {"d1": 2.0, "d2": -1.0, "c1": -1.0, "c2": 0.5, "c3": 0.25}
        dates = {"d1": "2026-01-07", "d2": "2026-01-08", "c1": "2026-01-14", "c2": "2026-01-21", "c3": "2026-01-22"}
        self.dates = dates
        pd.DataFrame([{
            "date": dates[k], "signed_return_pct": v, "abs_return_pct": abs(v),
            "range_pct": abs(v) * 2, "scaled_abs_move": abs(v) * 10,
        } for k, v in signed.items()]).to_csv(self.sessions_path, index=False)
        rows = [
            ("main", "A", "cpi", "d1", "c1"), ("main", "A", "cpi", "d1", "c2"),
            ("main", "B", "ppi", "d2", "c2"), ("main", "B", "ppi", "d2", "c3"),
            ("full", "A", "cpi", "d1", "c1"),
        ]
        pd.DataFrame([{
            "sample": s, "event_id": e, "event_type": t,
            "event_session_date": dates[d], "control_session_date": dates[c],
        } for s, e, t, d, c in rows]).to_csv(self.matches_path, index=False)

    def tearDown(self):
        self.temp.cleanup()

    def _get(self, result, sample, group, measure, statistic):
        return result[(result["sample"] == sample) & (result.group == group)
                      & (result.measure == measure) & (result.statistic == statistic)].iloc[0]

    def test_pooled_hand_checked_medians_counts_and_ratio(self):
        result = compare_release_and_ordinary_days(self.matches_path, self.sessions_path)
        self.assertEqual(result.columns.tolist(), SUMMARY_COLUMNS)
        row = self._get(result, "main", "all_three", "abs_return_pct", "median")
        self.assertAlmostEqual(row.release_value, 1.5)      # events: [2, 1]
        self.assertAlmostEqual(row.ordinary_value, 0.5)     # pairs: [1, 0.5, 0.5, 0.25]
        self.assertAlmostEqual(row.difference, 1.0)
        self.assertAlmostEqual(row.ratio, 3.0)
        self.assertEqual((row.n_events, row.n_pairs, row.n_unique_ordinary_days), (2, 4, 3))

    def test_groups_use_only_their_own_events_and_pairs(self):
        result = compare_release_and_ordinary_days(self.matches_path, self.sessions_path)
        row = self._get(result, "main", "cpi", "scaled_abs_move", "median")
        self.assertAlmostEqual(row.release_value, 20.0)
        self.assertAlmostEqual(row.ordinary_value, 7.5)
        self.assertEqual(row.n_events, 1)
        full = self._get(result, "full", "all_three", "range_pct", "median")
        self.assertEqual((full.n_events, full.n_pairs), (1, 1))
        self.assertEqual(result["sample"].iloc[0], "main")

    def test_percentiles_use_linear_interpolation(self):
        result = compare_release_and_ordinary_days(self.matches_path, self.sessions_path)
        row = self._get(result, "main", "all_three", "abs_return_pct", "p90")
        self.assertAlmostEqual(row.ordinary_value, pd.Series([1, 0.5, 0.5, 0.25]).quantile(0.9))

    def test_direction_statistics(self):
        result = compare_release_and_ordinary_days(self.matches_path, self.sessions_path)
        row = self._get(result, "main", "all_three", "signed_return_pct", "share_positive")
        self.assertAlmostEqual(row.release_value, 0.5)
        self.assertAlmostEqual(row.ordinary_value, 0.75)
        median = self._get(result, "main", "all_three", "signed_return_pct", "median")
        self.assertAlmostEqual(median.release_value, 0.5)
        self.assertTrue(pd.isna(median.ratio))
        self.assertTrue(pd.isna(row.ratio))

    def test_rejects_match_dates_missing_from_sessions(self):
        matches = pd.read_csv(self.matches_path)
        matches.loc[0, "control_session_date"] = "2030-01-01"
        matches.to_csv(self.matches_path, index=False)
        with self.assertRaisesRegex(ValueError, "missing from session outcomes"):
            compare_release_and_ordinary_days(self.matches_path, self.sessions_path)

    def test_save_rounds_and_keeps_columns(self):
        result = compare_release_and_ordinary_days(self.matches_path, self.sessions_path)
        path = save_comparison(result, Path(self.temp.name) / "out.csv")
        saved = pd.read_csv(path)
        self.assertEqual(saved.columns.tolist(), SUMMARY_COLUMNS)
        self.assertEqual(len(saved), len(result))


if __name__ == "__main__":
    unittest.main()
