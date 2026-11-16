import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from event_reactions import REACTION_COLUMNS, calculate_event_reactions, save_event_reactions


EVENT_COLUMNS = [
    "event_id", "event_origin", "event_type", "indicator", "event_name",
    "public_timestamp_utc", "event_date_et", "overlap_flag", "overlap_group_id",
    "overlap_policy",
]
GOLD_COLUMNS = ["date", "open", "high", "low", "close", "ticker", "source"]


class EventReactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.events_path = root / "events.csv"
        self.gold_path = root / "gold.csv"
        pd.DataFrame([
            ["event-a", "scheduled", "core_cpi_mom", "core_cpi_mom", "CPI", "2026-01-05T13:30:00+00:00", "2026-01-05", False, "", "eligible_for_single_event_analysis"],
            ["event-b", "unscheduled", "sanctions", "", "News", "2026-01-06T15:00:00+00:00", "2026-01-06", True, "overlap:abc", "exclude_from_single_event_analysis"],
            ["event-future", "scheduled", "cpi", "cpi", "Future", "2026-01-13T13:30:00+00:00", "2026-01-13", False, "", "eligible_for_single_event_analysis"],
        ], columns=EVENT_COLUMNS).to_csv(self.events_path, index=False)
        pd.DataFrame([
            ["2026-01-02", 100, 102, 99, 100, "GC=F", "Yahoo"],
            ["2026-01-05", 100, 103, 99, 102, "GC=F", "Yahoo"],
            ["2026-01-06", 102, 104, 101, 103, "GC=F", "Yahoo"],
            ["2026-01-07", 103, 105, 102, 104, "GC=F", "Yahoo"],
            ["2026-01-08", 104, 106, 103, 105, "GC=F", "Yahoo"],
            ["2026-01-09", 105, 107, 104, 106, "GC=F", "Yahoo"],
            ["2026-01-12", 106, 108, 105, 107, "GC=F", "Yahoo"],
        ], columns=GOLD_COLUMNS).to_csv(self.gold_path, index=False)

    def tearDown(self):
        self.temp.cleanup()

    def test_calculates_close_to_close_trading_session_horizons(self):
        result = calculate_event_reactions(self.events_path, self.gold_path)
        self.assertEqual(result.columns.tolist(), REACTION_COLUMNS)
        row = result.loc[result.event_id == "event-a"].iloc[0]
        self.assertEqual(row.analysis_status, "ok")
        self.assertEqual(row.gold_session_alignment, "same_date")
        self.assertAlmostEqual(row.event_session_return_pct, 2.0)
        self.assertAlmostEqual(row.event_session_range_pct, 4.0)
        self.assertAlmostEqual(row.return_1_sessions_pct, 3.0)
        self.assertAlmostEqual(row.return_3_sessions_pct, 5.0)
        self.assertAlmostEqual(row.return_5_sessions_pct, 7.0)

    def test_retains_overlap_rows_but_marks_them_ineligible(self):
        result = calculate_event_reactions(self.events_path, self.gold_path)
        row = result.loc[result.event_id == "event-b"].iloc[0]
        self.assertFalse(row.single_event_eligible)
        self.assertEqual(row.overlap_group_id, "overlap:abc")

    def test_future_event_is_retained_with_no_future_gold_status(self):
        result = calculate_event_reactions(self.events_path, self.gold_path)
        row = result.loc[result.event_id == "event-future"].iloc[0]
        self.assertEqual(row.analysis_status, "no_gold_session_on_or_after_event_date")
        self.assertEqual(row.event_session_return_pct, "")

    def test_rejects_duplicate_gold_sessions(self):
        gold = pd.read_csv(self.gold_path)
        gold = pd.concat([gold, gold.iloc[[0]]], ignore_index=True)
        gold.to_csv(self.gold_path, index=False)
        with self.assertRaisesRegex(ValueError, "unique"):
            calculate_event_reactions(self.events_path, self.gold_path)


    def test_saved_output_rounds_float_noise_and_keeps_blanks(self):
        result = calculate_event_reactions(self.events_path, self.gold_path)
        result.loc[result.event_id == "event-a", "event_session_return_pct"] = 2.0000000000000036
        out = save_event_reactions(result, Path(self.temp.name) / "out.csv")
        saved = pd.read_csv(out, dtype=str, keep_default_na=False)
        row = saved.loc[saved.event_id == "event-a"].iloc[0]
        self.assertEqual(row.event_session_return_pct, "2.0")
        future = saved.loc[saved.event_id == "event-future"].iloc[0]
        self.assertEqual(future.event_session_return_pct, "")


if __name__ == "__main__":
    unittest.main()
