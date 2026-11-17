import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vol_probabilities import (brier, calibration_table, climatology, log_loss, probs_from_abs_sample,
                               probs_normal, range_index, walk_forward_probabilities)


class MoveRangeTests(unittest.TestCase):
    def test_range_index_edges(self):
        self.assertEqual(range_index([0.0, 0.49, 0.5, 0.99, 1.0, 1.99, 2.0, 5.0]).tolist(),
                         [0, 0, 1, 1, 2, 2, 3, 3])

    def test_empirical_probabilities_by_hand(self):
        abs_z = np.sort(np.array([0.1, 0.3, 0.6, 0.9, 1.5, 2.5, 3.0, 0.2]))
        p = probs_from_abs_sample(abs_z, [1.0])[0]
        # |r| = |z|: <0.5: 0.1,0.2,0.3 ; 0.5-1: 0.6,0.9 ; 1-2: 1.5 ; >=2: 2.5,3.0
        np.testing.assert_allclose(p, [3 / 8, 2 / 8, 1 / 8, 2 / 8])
        p2 = probs_from_abs_sample(abs_z, [2.0])[0]           # doubles every move
        # |r| = 0.2,0.4,0.6,1.2,1.8,3.0,5.0,6.0
        np.testing.assert_allclose(p2, [2 / 8, 1 / 8, 2 / 8, 3 / 8])

    def test_normal_probabilities(self):
        p = probs_normal([1.0])[0]
        cdf = lambda x: math.erf(x / math.sqrt(2))
        np.testing.assert_allclose(p, [cdf(0.5), cdf(1) - cdf(0.5), cdf(2) - cdf(1), 1 - cdf(2)])
        self.assertAlmostEqual(p.sum(), 1.0)

    def test_climatology_uses_returns_up_to_origin(self):
        r = pd.DataFrame({"ret_pct": [0.1, 3.0, 0.7, -1.5]})
        c = climatology(r, 1, 3)
        np.testing.assert_allclose(c[0], [0.5, 0, 0, 0.5])          # returns 0..1
        np.testing.assert_allclose(c[1], [1 / 3, 1 / 3, 0, 1 / 3])  # returns 0..2

    def test_scores(self):
        p = np.array([[0.7, 0.2, 0.1, 0.0]])
        self.assertAlmostEqual(brier(p, np.array([0]))[0], 0.09 + 0.04 + 0.01)
        self.assertAlmostEqual(log_loss(p, np.array([3]))[0], -math.log(1e-6))

    def test_walk_forward_no_look_ahead_and_calibrated_on_simulated_data(self):
        rng = np.random.default_rng(5)
        n, omega, alpha, beta = 4000, 0.05, 0.05, 0.9
        var, ret = omega / (1 - alpha - beta), []
        for _ in range(n):
            r = rng.standard_t(6) * np.sqrt(var * 4 / 6); ret.append(r); var = omega + alpha * r * r + beta * var
        dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2005-01-03", periods=n)]
        returns = pd.DataFrame({"date": dates, "ret_pct": ret})
        fitter = lambda x: (omega, alpha, beta, True)
        res = walk_forward_probabilities(returns, dates[1500], fitter, refit_every=21)
        valid = ~np.isnan(res["fhs"]).any(axis=1) & (res["outcome"] >= 0)
        np.testing.assert_allclose(res["fhs"][valid].sum(axis=1), 1)
        for j in range(4):   # FHS is calibrated on average for fat-tailed simulated returns
            self.assertAlmostEqual(res["fhs"][valid, j].mean(), (res["outcome"][valid] == j).mean(), delta=0.03)
        changed = returns.copy(); changed.loc[2000, "ret_pct"] = 50.0
        res2 = walk_forward_probabilities(changed, dates[1500], fitter, refit_every=21)
        np.testing.assert_allclose(res["fhs"][:2000], res2["fhs"][:2000])   # no forecast before 2000 sees r_2000
        table = calibration_table(res["fhs"][valid], res["outcome"][valid])
        self.assertTrue(set(table["range"]) == {"lt_0.5", "0.5_1", "1_2", "ge_2"})


if __name__ == "__main__":
    unittest.main()
