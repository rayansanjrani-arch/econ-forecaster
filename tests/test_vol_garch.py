import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vol_garch import garch_one_step, multi_step_sum, walk_forward_garch

HAS_ARCH = importlib.util.find_spec("arch") is not None


def _simulate(n, omega=0.05, alpha=0.08, beta=0.9, seed=0):
    rng = np.random.default_rng(seed)
    var, out = omega / (1 - alpha - beta), []
    for _ in range(n):
        r = rng.normal(0, np.sqrt(var))
        out.append(r)
        var = omega + alpha * r * r + beta * var
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2005-01-03", periods=n)]
    return pd.DataFrame({"date": dates, "ret_pct": out})


class GarchRecursionTests(unittest.TestCase):
    def test_one_step_recursion_by_hand(self):
        f = garch_one_step([1.0, 4.0], omega=0.1, alpha=0.2, beta=0.7, init_var=2.0)
        self.assertAlmostEqual(f[0], 0.1 + 0.2 * 1.0 + 0.7 * 2.0)
        self.assertAlmostEqual(f[1], 0.1 + 0.2 * 4.0 + 0.7 * f[0])

    def test_multi_step_sum_by_hand_and_mean_reversion(self):
        total = multi_step_sum([2.0], omega=0.1, alpha=0.1, beta=0.8, h=3)
        s2 = 0.1 + 0.9 * 2.0; s3 = 0.1 + 0.9 * s2
        self.assertAlmostEqual(total[0], 2.0 + s2 + s3)
        long_run = 0.1 / (1 - 0.9)
        self.assertLess(multi_step_sum([5.0], 0.1, 0.1, 0.8, 5)[0], 25.0)   # high vol reverts down
        self.assertGreater(multi_step_sum([0.2], 0.1, 0.1, 0.8, 5)[0], 1.0)  # low vol reverts up
        self.assertAlmostEqual(multi_step_sum([long_run], 0.1, 0.1, 0.8, 5)[0], 5 * long_run)

    def test_walk_forward_uses_only_past_data_and_refits_on_schedule(self):
        r = _simulate(400)
        seen = []
        def fake_fitter(x):
            seen.append(len(x))
            return 0.05, 0.08, 0.9, True
        f, log = walk_forward_garch(r, r["date"].iloc[300], refit_every=21, fitter=fake_fitter)
        self.assertEqual(seen, [301, 322, 343, 364, 385])
        self.assertTrue(f.iloc[:300].isna().all().all())
        self.assertFalse(f.iloc[300:].isna().any().any())
        changed = r.copy(); changed.loc[350, "ret_pct"] = 40.0
        g, _ = walk_forward_garch(changed, r["date"].iloc[300], refit_every=21, fitter=fake_fitter)
        pd.testing.assert_frame_equal(f.iloc[:350], g.iloc[:350])   # forecasts before origin 350 never see r_350
        self.assertNotAlmostEqual(f.iloc[350, 0], g.iloc[350, 0])    # the origin-350 forecast does use it

    def test_non_converged_fit_keeps_previous_parameters(self):
        r = _simulate(200)
        results = iter([(0.05, 0.08, 0.9, True), (9.0, 0.5, 0.5, False)])
        _, log = walk_forward_garch(r, r["date"].iloc[150], refit_every=30, fitter=lambda x: next(results))
        self.assertEqual(log["used_params"].tolist(), ["new", "previous"])


@unittest.skipUnless(HAS_ARCH, "arch package not installed")
class GarchFitTests(unittest.TestCase):
    def test_fit_recovers_simulated_parameters(self):
        from vol_garch import fit_garch
        r = _simulate(4000, seed=4)
        omega, alpha, beta, converged = fit_garch(r["ret_pct"])
        self.assertTrue(converged)
        self.assertAlmostEqual(alpha, 0.08, delta=0.04)
        self.assertAlmostEqual(beta, 0.90, delta=0.05)


if __name__ == "__main__":
    unittest.main()
