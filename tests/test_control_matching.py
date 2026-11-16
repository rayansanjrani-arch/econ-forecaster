import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from control_matching import MATCH_COLUMNS, match_controls


REACTION_COLUMNS = ["event_id", "event_type", "single_event_eligible", "analysis_status", "gold_event_session_date"]


class ControlMatchingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.sessions_path = root / "sessions.csv"
        self.reactions_path = root / "reactions.csv"
        # 81 consecutive weekdays with no holidays: same weekday every 5 sessions.
        self.dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-01-05", periods=81)]
        self.vol = ["1.0"] * len(self.dates)
        self.p = 40  # event position (a Wednesday-aligned session in the middle)
        self._write_sessions()
        self.events = [["e1", "cpi", "True", "ok", self.dates[self.p]]]
        self._write_reactions()

    def tearDown(self):
        self.temp.cleanup()

    def _write_sessions(self):
        pd.DataFrame({"date": self.dates, "trailing_vol_pct": self.vol}).to_csv(self.sessions_path, index=False)

    def _write_reactions(self):
        pd.DataFrame(self.events, columns=REACTION_COLUMNS).to_csv(self.reactions_path, index=False)

    def _distances(self, **kwargs):
        matches, summary = match_controls(self.reactions_path, self.sessions_path, "main", None, **kwargs)
        return matches.session_distance.tolist(), matches, summary

    def test_same_weekday_nearest_five_with_earlier_tie_first(self):
        distances, matches, summary = self._distances()
        self.assertEqual(matches.columns.tolist(), MATCH_COLUMNS)
        self.assertEqual(distances, [-5, 5, -10, 10, -15])
        self.assertEqual(matches.control_rank.tolist(), [1, 2, 3, 4, 5])
        weekdays = pd.to_datetime(matches.control_session_date).dt.day_of_week.unique().tolist()
        self.assertEqual(weekdays, [pd.Timestamp(self.dates[self.p]).day_of_week])
        self.assertEqual(summary.n_controls.tolist(), [5])

    def test_excludes_release_days_and_adjacent_sessions_but_does_not_match_overlaps(self):
        self.events += [
            ["e2-overlap", "ppi", "False", "ok", self.dates[self.p + 5]],
            ["e3-future", "ppi", "True", "no_gold_session_on_or_after_event_date", ""],
            ["e4", "empsit", "True", "ok", self.dates[self.p + 9]],
        ]
        self._write_reactions()
        matches, summary = match_controls(self.reactions_path, self.sessions_path, "main", None)
        e1 = matches[matches.event_id == "e1"].session_distance.tolist()
        # +5 is a release day; +10 is next to the e4 release day at +9.
        self.assertEqual(e1, [-5, -10, -15, 15, -20])
        self.assertNotIn("e2-overlap", set(summary.event_id))
        self.assertNotIn("e3-future", set(summary.event_id))
        release_days = {self.dates[self.p], self.dates[self.p + 5], self.dates[self.p + 9]}
        self.assertFalse(set(matches.control_session_date) & release_days)

    def test_sample_start_applies_to_events_and_comparison_days(self):
        start = self.dates[self.p - 2]
        matches, summary = match_controls(self.reactions_path, self.sessions_path, "main", start)
        self.assertEqual(matches.session_distance.tolist(), [5, 10, 15, 20, 25])
        later = self.dates[self.p + 1]
        matches, summary = match_controls(self.reactions_path, self.sessions_path, "main", later)
        self.assertTrue(matches.empty and summary.empty)

    def test_records_fewer_than_target_and_skips_missing_volatility(self):
        self.vol[self.p - 5] = ""
        self._write_sessions()
        distances, _, summary = self._distances(window=12)
        self.assertEqual(distances, [5, -10, 10])
        self.assertEqual(summary.n_controls.tolist(), [3])

    def test_rerun_gives_identical_output(self):
        first, _ = match_controls(self.reactions_path, self.sessions_path, "main", None)
        second, _ = match_controls(self.reactions_path, self.sessions_path, "main", None)
        pd.testing.assert_frame_equal(first, second)

    def test_rejects_event_session_missing_from_sessions(self):
        self.events.append(["e9", "cpi", "True", "ok", "2030-01-01"])
        self._write_reactions()
        with self.assertRaisesRegex(ValueError, "missing from session outcomes"):
            match_controls(self.reactions_path, self.sessions_path, "main", None)


if __name__ == "__main__":
    unittest.main()
