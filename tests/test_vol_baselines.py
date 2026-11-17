import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vol_baselines import EWMA_LAMBDA, baseline_forecasts, best_baseline, score_baselines, summarise


def _returns(values, start="2007-09-03"):
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, periods=len(values))]
    return pd.DataFrame({"date": dates, "ret_pct": values})


class VolBaselineTests(unittest.TestCase):
    def test_hv_uses_last_window_of_squared_returns_only(self):
        r = _returns(list(np.arange(1, 81, dtype=float)))
        f = baseline_forecasts(r)
        self.assertTrue(np.isnan(f.loc[18, "hv20"]))
        self.assertAlmostEqual(f.loc[19, "hv20"], np.mean(np.arange(1, 21) ** 2))
        self.assertAlmostEqual(f.loc[79, "hv60"], np.mean(np.arange(21, 81) ** 2))

    def test_ewma_recursion_and_no_look_ahead(self):
        values = list(np.random.default_rng(1).normal(0, 1, 100))
        r = _returns(values)
        f = baseline_forecasts(r)
        sq = np.array(values) ** 2
        var = sq[:60].mean()
        var = EWMA_LAMBDA * var + (1 - EWMA_LAMBDA) * sq[59]
        self.assertAlmostEqual(f.loc[59, "ewma"], var)
        var = EWMA_LAMBDA * var + (1 - EWMA_LAMBDA) * sq[60]
        self.assertAlmostEqual(f.loc[60, "ewma"], var)
        changed = list(values); changed[90] = 25.0
        g = baseline_forecasts(_returns(changed))
        pd.testing.assert_frame_equal(f.iloc[:90], g.iloc[:90])

    def test_scoring_scales_horizon_and_ranks_true_model_best(self):
        rng = np.random.default_rng(3)
        sigma = np.where(np.arange(1500) % 300 < 150, 0.5, 2.0)   # regime switches
        r = _returns(list(rng.normal(0, sigma)), start="2007-06-01")
        table = score_baselines(r)
        self.assertTrue(np.allclose(table["f_hv20_5"], 5 * table["f_hv20_1"]))
        self.assertTrue((table.loc[table.window == "", "date"] < "2008-01-01").all())
        summary = summarise(table)
        self.assertIn(best_baseline(summary, 1), {"hv20", "ewma"})  # fast-adapting wins on switching regimes


if __name__ == "__main__":
    unittest.main()
