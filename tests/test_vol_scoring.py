import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vol_scoring import (assign_window, keep_decision, log_returns, moving_block_bootstrap_ci,
                         mse, qlike, realized_variance)


class VolScoringTests(unittest.TestCase):
    def test_log_returns_sorted_and_in_percent(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "g.csv"
            pd.DataFrame({"date": ["2020-01-03", "2020-01-02", "2020-01-06"],
                          "close": [110.0, 100.0, 99.0]}).to_csv(path, index=False)
            r = log_returns(path)
        self.assertEqual(r["date"].tolist(), ["2020-01-03", "2020-01-06"])
        self.assertAlmostEqual(r["ret_pct"].iloc[0], np.log(1.1) * 100)

    def test_realized_variance_uses_only_future_returns(self):
        r = pd.DataFrame({"date": list("abcdefg"), "ret_pct": [1.0, 2.0, -1.0, 3.0, 0.0, 2.0, 1.0]})
        rv = realized_variance(r, horizons=(1, 3))
        self.assertEqual(rv.loc[0, "rv_1"], 4.0)            # next return 2
        self.assertEqual(rv.loc[0, "rv_3"], 4 + 1 + 9)       # next three: 2, -1, 3
        self.assertTrue(np.isnan(rv.loc[6, "rv_1"]))
        self.assertTrue(np.isnan(rv.loc[4, "rv_3"]))
        # changing the origin's own return does not change its target
        r2 = r.copy(); r2.loc[0, "ret_pct"] = 50.0
        self.assertEqual(realized_variance(r2, horizons=(1,)).loc[0, "rv_1"], 4.0)

    def test_qlike_minimised_at_true_variance_and_defined_at_zero(self):
        grid = np.linspace(0.5, 4, 351)
        self.assertAlmostEqual(grid[np.argmin(qlike(grid, 2.0))], 2.0, places=2)
        self.assertAlmostEqual(float(qlike([1.0], [0.0])[0]), 0.0)
        with self.assertRaises(ValueError):
            qlike([0.0], [1.0])
        self.assertEqual(float(mse([3.0], [1.0])[0]), 4.0)

    def test_window_assignment_and_burn_in(self):
        w = assign_window(["2007-12-31", "2008-01-02", "2015-12-31", "2016-01-04", "2026-11-13"])
        self.assertEqual(list(w), ["", "W1", "W2", "W3", "W5"])

    def test_block_bootstrap_reproducible_and_centred(self):
        x = np.random.default_rng(0).normal(1.0, 1.0, 600)
        a = moving_block_bootstrap_ci(x, block=21, resamples=500, seed=1)
        b = moving_block_bootstrap_ci(x, block=21, resamples=500, seed=1)
        self.assertEqual(a, b)
        self.assertLess(a[0], x.mean()); self.assertGreater(a[1], x.mean())
        with self.assertRaises(ValueError):
            moving_block_bootstrap_ci(x[:10], block=21)

    def test_keep_rule(self):
        n = 400
        windows = np.repeat(["W1", "W2", "W3", "W4", "W5"], n // 5)
        rng = np.random.default_rng(2)
        base = rng.normal(2.0, 0.3, n)
        better = pd.DataFrame({"window": windows, "cand": base - 0.2, "base": base})
        d = keep_decision(better, "cand", "base", resamples=300)
        self.assertTrue(d["keep"]); self.assertEqual(d["windows_won"], 5)
        # wins overall but only in 3 of 5 windows -> not kept
        cand = base.copy(); cand[: 2 * n // 5] += 0.5; cand[2 * n // 5:] -= 0.6
        mixed = pd.DataFrame({"window": windows, "cand": cand, "base": base})
        d = keep_decision(mixed, "cand", "base", resamples=300)
        self.assertEqual(d["windows_won"], 3); self.assertFalse(d["keep"])
        # burn-in rows are ignored
        burn = pd.concat([better, pd.DataFrame({"window": [""], "cand": [999.0], "base": [0.0]})])
        self.assertTrue(keep_decision(burn, "cand", "base", resamples=300)["keep"])


if __name__ == "__main__":
    unittest.main()
