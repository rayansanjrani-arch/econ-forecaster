import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vol_events import estimate_delta, release_session_flags, walk_forward_event_garch
from vol_garch import walk_forward_garch


def _returns(n, seed=0, release_every=20, boost=3.0):
    rng = np.random.default_rng(seed)
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2005-01-03", periods=n)]
    flags = np.zeros(n, dtype=bool); flags[::release_every] = True
    sd = np.where(flags, np.sqrt(boost), 1.0)
    return pd.DataFrame({"date": dates, "ret_pct": rng.normal(0, sd)}), flags


class ReleaseFlagTests(unittest.TestCase):
    def test_flags_map_to_first_session_on_or_after_release(self):
        with tempfile.TemporaryDirectory() as temp:
            cal = Path(temp) / "cal.csv"
            pd.DataFrame({"release_date": ["2010-04-02", "2010-04-07", "2010-04-07", "2010-05-20", "2010-03-01"],
                          "indicator": ["employment_situation", "ppi", "core_cpi_mom", "retail_sales_advance", "ppi"]}
                         ).to_csv(cal, index=False)
            sessions = ["2010-04-01", "2010-04-05", "2010-04-06", "2010-04-07", "2010-05-20"]
            flags = release_session_flags(sessions, [cal])
        # Good Friday release -> Monday; retail ignored; release before the first session (gap > 5 days) ignored
        self.assertEqual(flags.tolist(), [False, True, False, True, False])


class EventGarchTests(unittest.TestCase):
    params = (0.05, 0.05, 0.9)

    def test_delta_recovers_release_variance_ratio(self):
        r, flags = _returns(6000, boost=3.0)
        delta = estimate_delta(r["ret_pct"].to_numpy() ** 2, flags, self.params,
                               init_var=1.0, end=5999)
        self.assertAlmostEqual(delta, 2.0, delta=0.5)

    def test_zero_delta_reproduces_base_garch_and_flags_only_scale_release_steps(self):
        r, _ = _returns(400)
        no_flags = np.zeros(len(r), dtype=bool)
        fitter = lambda x: (*self.params, True)
        ev, _ = walk_forward_event_garch(r, no_flags, r["date"].iloc[200], fitter, refit_every=21)
        base, _ = walk_forward_garch(r, r["date"].iloc[200], refit_every=21, fitter=fitter)
        np.testing.assert_allclose(ev["f_garchev_1"].iloc[200:], base["f_garch_1"].iloc[200:])
        np.testing.assert_allclose(ev["f_garch_5"].iloc[200:], base["f_garch_5"].iloc[200:])

    def test_adjustment_applies_only_to_flagged_future_sessions(self):
        r, flags = _returns(400, release_every=20)
        fitter = lambda x: (*self.params, True)
        ev, log = walk_forward_event_garch(r, flags, r["date"].iloc[200], fitter, refit_every=21)
        d = ev["delta"].iloc[250]
        self.assertGreater(d, 0)
        t_rel = 259            # flags[260] is True -> origin 259 predicts a release session
        self.assertAlmostEqual(ev["f_garchev_1"].iloc[t_rel], ev["f_garch_1"].iloc[t_rel] * (1 + d))
        self.assertAlmostEqual(ev["f_garchev_1"].iloc[t_rel + 1], ev["f_garch_1"].iloc[t_rel + 1])
        self.assertGreater(ev["f_garchev_5"].iloc[256], ev["f_garch_5"].iloc[256])   # release at t+4
        self.assertAlmostEqual(ev["f_garchev_5"].iloc[261], ev["f_garch_5"].iloc[261])  # none in t+1..t+5

    def test_delta_uses_training_data_only(self):
        r, flags = _returns(400)
        fitter = lambda x: (*self.params, True)
        _, log1 = walk_forward_event_garch(r, flags, r["date"].iloc[200], fitter, refit_every=21)
        r2 = r.copy(); r2.loc[300:, "ret_pct"] *= 10
        _, log2 = walk_forward_event_garch(r2, flags, r["date"].iloc[200], fitter, refit_every=21)
        refits_before = log1["refit_origin"] < r["date"].iloc[300]
        np.testing.assert_allclose(log1.loc[refits_before, "delta"], log2.loc[refits_before, "delta"])


if __name__ == "__main__":
    unittest.main()
