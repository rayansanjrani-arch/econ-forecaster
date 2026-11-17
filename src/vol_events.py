"""Task 3.4: GARCH(1,1) forecasts scaled on scheduled BLS release sessions.

Release dates come from schedules published in advance, so flags for sessions
t+1..t+h are known at the close of t. The scale factor delta is re-estimated at
each refit from training data only.
"""

import numpy as np
import pandas as pd

from config import VOL_REFIT_EVERY
from vol_garch import INIT_RETURNS, garch_one_step

RELEASE_INDICATORS = ("core_cpi_mom", "ppi", "employment_situation")
MAX_ALIGNMENT_GAP_DAYS = 5


def release_session_flags(session_dates, calendar_paths, indicators=RELEASE_INDICATORS):
    """Boolean per session: True if a release maps to it (first session on/after the date, <= 5 days)."""
    sessions = pd.to_datetime(pd.Series(session_dates)).to_numpy()
    releases = []
    for path in calendar_paths:
        cal = pd.read_csv(path, dtype={"release_date": str})
        releases.extend(cal.loc[cal["indicator"].isin(indicators), "release_date"])
    flags = np.zeros(len(sessions), dtype=bool)
    for day in sorted(set(releases)):
        d = np.datetime64(day)
        idx = int(np.searchsorted(sessions, d))
        if idx < len(sessions) and (sessions[idx] - d).astype("timedelta64[D]").astype(int) <= MAX_ALIGNMENT_GAP_DAYS:
            flags[idx] = True
    return flags


def estimate_delta(sq, flags, params, init_var, end):
    """delta from returns 1..end: mean z^2 on release sessions / other sessions - 1."""
    one = garch_one_step(sq[:end], *params, init_var)       # one[t] = variance forecast for t+1
    z2 = sq[1:end + 1] / one[:end]                          # returns 1..end over their forecasts
    f = flags[1:end + 1]
    if f.sum() == 0 or (~f).sum() == 0:
        return 0.0
    return float(z2[f].mean() / z2[~f].mean() - 1)


def params_from_log(fit_log):
    """Fitter replaying logged walk-forward parameters (checks training lengths)."""
    rows = iter(fit_log.to_dict("records"))
    def fitter(x):
        row = next(rows)
        if int(row["train_returns"]) != len(x):
            raise ValueError("Fit log does not match the walk-forward schedule")
        return row["omega"], row["alpha"], row["beta"], bool(row["converged"])
    return fitter


def walk_forward_event_garch(returns, flags, first_origin_date, fitter, horizons=(1, 5),
                             refit_every=VOL_REFIT_EVERY):
    """Base and release-adjusted GARCH forecasts for every origin from first_origin_date on."""
    ret = returns["ret_pct"].to_numpy(dtype=float)
    sq = ret ** 2
    n = len(ret)
    start = int(np.searchsorted(returns["date"].to_numpy(), first_origin_date))
    init_var = sq[:INIT_RETURNS].mean()
    out = {f"f_garch_{h}": np.full(n, np.nan) for h in horizons}
    out.update({f"f_garchev_{h}": np.full(n, np.nan) for h in horizons})
    out["delta"] = np.full(n, np.nan)
    log, params = [], None
    max_h = max(horizons)
    for refit_at in range(start, n, refit_every):
        omega, alpha, beta, converged = fitter(ret[: refit_at + 1])
        if converged or params is None:
            params = (omega, alpha, beta)
        delta = estimate_delta(sq, flags, params, init_var, refit_at)
        log.append({"refit_origin": returns["date"].iloc[refit_at], "delta": delta})
        stop = min(refit_at + refit_every, n)
        one = garch_one_step(sq[:stop], *params, init_var)[refit_at:stop]
        persistence = params[1] + params[2]
        steps = [one]
        for _ in range(max_h - 1):
            steps.append(params[0] + persistence * steps[-1])
        steps = np.vstack(steps)                                     # steps[k-1, j] = variance for t+k
        origins = np.arange(refit_at, stop)
        future = np.zeros_like(steps, dtype=bool)
        for k in range(max_h):
            idx = origins + k + 1
            valid = idx < n
            future[k, valid] = flags[idx[valid]]
        for h in horizons:
            out[f"f_garch_{h}"][refit_at:stop] = steps[:h].sum(axis=0)
            out[f"f_garchev_{h}"][refit_at:stop] = (steps[:h] * (1 + delta * future[:h])).sum(axis=0)
        out["delta"][refit_at:stop] = delta
    return pd.DataFrame(out, index=returns.index), pd.DataFrame(log)
