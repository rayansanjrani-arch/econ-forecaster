import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from event_comparison import compare_release_and_ordinary_days
from event_uncertainty import UNCERTAINTY_COLUMNS, bootstrap_comparison, verdict


def _write(root, release_values, control_values):
    """release_values[i] with control_values[i] (list) for event i, all in group 'cpi'."""
    dates = iter(d.strftime("%Y-%m-%d") for d in pd.bdate_range("2021-01-04", periods=500))
    session_rows, match_rows = [], []
    for i, (rv, cvs) in enumerate(zip(release_values, control_values)):
        ed = next(dates)
        session_rows.append((ed, rv))
        for cv in cvs:
            cd = next(dates)
            session_rows.append((cd, cv))
            match_rows.append({"sample": "main", "event_id": f"e{i}", "event_type": "cpi",
                               "event_session_date": ed, "control_session_date": cd})
    sessions = pd.DataFrame([{"date": d, "signed_return_pct": v, "abs_return_pct": v,
                              "range_pct": v, "scaled_abs_move": v} for d, v in session_rows])
    sessions.to_csv(root / "sessions.csv", index=False)
    pd.DataFrame(match_rows).to_csv(root / "matches.csv", index=False)
    return root / "matches.csv", root / "sessions.csv"


class EventUncertaintyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _primary(self, result, group="all_three"):
        return result[(result.group == group) & result.primary_test].iloc[0]

    def test_identical_release_and_ordinary_values_give_ratio_one_interval(self):
        m, s = _write(self.root, [1.0, 1.0, 1.0], [[1.0, 1.0]] * 3)
        result = bootstrap_comparison(m, s, resamples=200, seed=1)
        self.assertEqual(result.columns.tolist(), UNCERTAINTY_COLUMNS)
        row = self._primary(result)
        self.assertEqual((row.ratio, row.ratio_ci_low, row.ratio_ci_high), (1.0, 1.0, 1.0))
        self.assertEqual(row.verdict, "not_established")

    def test_point_estimates_match_task_2_3_3(self):
        rng = np.random.default_rng(0)
        rel = list(rng.uniform(0.5, 2, 12))
        ctl = [list(rng.uniform(0.2, 1, 5)) for _ in range(12)]
        m, s = _write(self.root, rel, ctl)
        boot = bootstrap_comparison(m, s, resamples=50, seed=1)
        desc = compare_release_and_ordinary_days(m, s)
        for measure in ("abs_return_pct", "scaled_abs_move"):
            for stat in ("median", "p75", "p90"):
                b = boot[(boot.group == "cpi") & (boot.measure == measure) & (boot.statistic == stat)].iloc[0]
                d = desc[(desc.group == "cpi") & (desc.measure == measure) & (desc.statistic == stat)].iloc[0]
                self.assertAlmostEqual(b.ratio, d.ratio)
                self.assertAlmostEqual(b.difference, d.difference)
                self.assertLessEqual(b.ratio_ci_low, b.ratio_ci_high)

    def test_same_seed_reproduces_and_other_seed_differs(self):
        rng = np.random.default_rng(3)
        m, s = _write(self.root, list(rng.uniform(0, 2, 10)), [list(rng.uniform(0, 2, 5)) for _ in range(10)])
        a = bootstrap_comparison(m, s, resamples=100, seed=7)
        b = bootstrap_comparison(m, s, resamples=100, seed=7)
        c = bootstrap_comparison(m, s, resamples=100, seed=8)
        pd.testing.assert_frame_equal(a, b)
        self.assertFalse(np.allclose(a.ratio_ci_low, c.ratio_ci_low))

    def test_events_are_resampled_with_their_own_controls(self):
        # One event has huge controls; resampling by event keeps them together, so the
        # ordinary median jumps between clusters rather than mixing values freely.
        m, s = _write(self.root, [1.0, 1.0], [[0.1, 0.1, 0.1], [9.0, 9.0, 9.0]])
        row = self._primary(bootstrap_comparison(m, s, resamples=400, seed=2))
        self.assertAlmostEqual(row.ratio_ci_high, 10.0)      # only the low-control event drawn
        self.assertAlmostEqual(row.ratio_ci_low, 1 / 9.0)    # only the high-control event drawn

    def test_clear_large_effect_survives_and_strong_label(self):
        m, s = _write(self.root, [3.0] * 20, [[1.0] * 5] * 20)
        row = self._primary(bootstrap_comparison(m, s, resamples=100, seed=1))
        self.assertEqual(row.verdict, "strong")

    def test_verdict_rule(self):
        self.assertEqual(verdict(1.30, 1.05), "survives")
        self.assertEqual(verdict(1.30, 1.25), "strong")
        self.assertEqual(verdict(1.30, 0.95), "not_established")
        self.assertEqual(verdict(1.20, 1.10), "not_established")


if __name__ == "__main__":
    unittest.main()
