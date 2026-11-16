import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from event_reactions import calculate_event_reactions
from session_outcomes import OUTCOME_COLUMNS, calculate_session_outcomes, save_session_outcomes


GOLD_COLUMNS = ["date", "open", "high", "low", "close", "ticker", "source"]


def _write_gold(path, closes, dates=None):
    dates = dates or [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-01-05", periods=len(closes))]
    rows = [[d, c, c + 2, c - 1, c, "GC=F", "Yahoo"] for d, c in zip(dates, closes)]
    pd.DataFrame(rows, columns=GOLD_COLUMNS).to_csv(path, index=False)


class DataQualityFlagTests(unittest.TestCase):
    def test_flags_thin_volume_and_flat_bars_without_removing_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "gold.csv"
            pd.DataFrame([
                ["2026-01-05", 100, 101, 99, 100, 200000, "GC=F", "Yahoo"],
                ["2026-01-06", 101, 101, 101, 101, 5, "GC=F", "Yahoo"],
                ["2026-01-07", 102, 103, 101, 102, 0, "GC=F", "Yahoo"],
            ], columns=["date", "open", "high", "low", "close", "volume", "ticker", "source"]).to_csv(path, index=False)
            result = calculate_session_outcomes(path, window=2)
        self.assertEqual(len(result), 3)
        self.assertEqual(result["thin_volume_flag"].tolist(), [False, True, True])
        self.assertEqual(result["flat_bar_flag"].tolist(), [False, True, False])

    def test_missing_volume_column_leaves_flag_blank(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "gold.csv"
            _write_gold(path, [100.0, 101.0])
            result = calculate_session_outcomes(path, window=2)
        self.assertEqual(result["thin_volume_flag"].tolist(), ["", ""])


class SessionOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.gold_path = self.root / "gold.csv"
        # Hand-checkable: 100 -> 102 -> 99.96 -> 101.9592 -> 95.84 (approx)
        self.closes = [100.0, 102.0, 99.96, 101.9592, 95.841648]
        _write_gold(self.gold_path, self.closes)

    def tearDown(self):
        self.temp.cleanup()

    def test_hand_checkable_returns_range_and_volatility(self):
        result = calculate_session_outcomes(self.gold_path, window=3)
        self.assertEqual(result.columns.tolist(), OUTCOME_COLUMNS)
        self.assertTrue(np.isnan(result.loc[0, "signed_return_pct"]))
        self.assertAlmostEqual(result.loc[1, "signed_return_pct"], 2.0)
        self.assertAlmostEqual(result.loc[2, "signed_return_pct"], -2.0)
        self.assertAlmostEqual(result.loc[3, "signed_return_pct"], 2.0)
        self.assertAlmostEqual(result.loc[4, "signed_return_pct"], -6.0, places=5)
        self.assertAlmostEqual(result.loc[4, "abs_return_pct"], 6.0, places=5)
        # range = (high - low) / prior close = 3 / 101.9592
        self.assertAlmostEqual(result.loc[4, "range_pct"], 3 / 101.9592 * 100)
        # Session 4 volatility uses returns 1..3 only: std([2, -2, 2], ddof=1)
        expected_vol = np.std([2.0, -2.0, 2.0], ddof=1)
        self.assertAlmostEqual(result.loc[4, "trailing_vol_pct"], expected_vol)
        self.assertAlmostEqual(result.loc[4, "scaled_abs_move"], 6.0 / expected_vol, places=5)
        self.assertEqual(result["insufficient_history"].tolist(), [True, True, True, True, False])
        self.assertEqual(result["large_move_flag"].tolist(), [False, False, False, False, True])

    def test_session_volatility_does_not_use_its_own_close(self):
        before = calculate_session_outcomes(self.gold_path, window=3)
        changed = list(self.closes)
        changed[4] = 150.0
        _write_gold(self.gold_path, changed)
        after = calculate_session_outcomes(self.gold_path, window=3)
        self.assertAlmostEqual(before.loc[4, "trailing_vol_pct"], after.loc[4, "trailing_vol_pct"])
        self.assertNotAlmostEqual(before.loc[4, "signed_return_pct"], after.loc[4, "signed_return_pct"])

    def test_holiday_gap_return_spans_observed_sessions(self):
        dates = ["2026-01-02", "2026-01-05", "2026-01-07"]  # 2026-01-06 missing
        _write_gold(self.gold_path, [100.0, 101.0, 103.02], dates=dates)
        result = calculate_session_outcomes(self.gold_path, window=2)
        self.assertEqual(result.loc[2, "prior_session_date"], "2026-01-05")
        self.assertAlmostEqual(result.loc[2, "signed_return_pct"], 2.0)

    def test_matches_task_2_2_event_session_values(self):
        closes = [100.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
        _write_gold(self.gold_path, closes)
        events = self.root / "events.csv"
        pd.DataFrame([{
            "event_id": "e1", "event_origin": "scheduled", "event_type": "cpi",
            "indicator": "cpi", "event_name": "CPI",
            "public_timestamp_utc": "2026-01-06T13:30:00+00:00", "event_date_et": "2026-01-06",
            "overlap_flag": False, "overlap_group_id": "",
            "overlap_policy": "eligible_for_single_event_analysis",
        }]).to_csv(events, index=False)
        reaction = calculate_event_reactions(events, self.gold_path).iloc[0]
        session = calculate_session_outcomes(self.gold_path, window=2).set_index("date").loc["2026-01-06"]
        self.assertAlmostEqual(session.signed_return_pct, reaction.event_session_return_pct)
        self.assertAlmostEqual(session.range_pct, reaction.event_session_range_pct)

    def test_rejects_too_small_window(self):
        with self.assertRaisesRegex(ValueError, "at least 2"):
            calculate_session_outcomes(self.gold_path, window=1)

    def test_saved_file_keeps_blanks_for_missing_values(self):
        result = calculate_session_outcomes(self.gold_path, window=3)
        out = save_session_outcomes(result, self.root / "out.csv")
        saved = pd.read_csv(out, dtype=str, keep_default_na=False)
        self.assertEqual(saved.loc[0, "signed_return_pct"], "")
        self.assertEqual(saved.loc[0, "prior_session_date"], "")
        self.assertEqual(saved.loc[3, "trailing_vol_pct"], "")
        self.assertNotEqual(saved.loc[4, "trailing_vol_pct"], "")


if __name__ == "__main__":
    unittest.main()
