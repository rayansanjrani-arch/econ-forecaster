"""Task 3.3: walk-forward zero-mean GARCH(1,1) variance forecasts.

Parameters are estimated with the `arch` package on an expanding window up to
each refit origin and held fixed until the next refit; the variance recursion
only ever uses returns up to the forecast origin.
"""

import numpy as np
import pandas as pd

from config import VOL_REFIT_EVERY

INIT_RETURNS = 75


def garch_one_step(sq_returns, omega, alpha, beta, init_var):
    """variance[t] = forecast for t+1 made at close t: omega + alpha*r_t^2 + beta*var_t."""
    sq = np.asarray(sq_returns, dtype=float)
    out = np.empty(len(sq))
    var_t = init_var  # conditional variance of return 0
    for t in range(len(sq)):
        var_next = omega + alpha * sq[t] + beta * var_t
        out[t] = var_next
        var_t = var_next
    return out


def multi_step_sum(one_step, omega, alpha, beta, h):
    """Sum of GARCH forecasts for sessions t+1..t+h given the t+1 forecast."""
    one_step = np.asarray(one_step, dtype=float)
    total = one_step.copy()
    current = one_step.copy()
    for _ in range(h - 1):
        current = omega + (alpha + beta) * current
        total += current
    return total


def fit_garch(returns_pct):
    """Fit zero-mean GARCH(1,1); returns (omega, alpha, beta, converged)."""
    from arch import arch_model  # imported lazily so the rest of the module works without it
    model = arch_model(np.asarray(returns_pct, dtype=float), mean="Zero", vol="GARCH",
                       p=1, q=1, dist="normal", rescale=False)
    result = model.fit(disp="off", show_warning=False)
    params = result.params
    return (float(params["omega"]), float(params["alpha[1]"]), float(params["beta[1]"]),
            int(result.convergence_flag) == 0)


def walk_forward_garch(returns, first_origin_date, horizons=(1, 5), refit_every=VOL_REFIT_EVERY,
                       fitter=fit_garch):
    """Forecasts for every origin from first_origin_date on; returns (forecasts, fit_log)."""
    ret = returns["ret_pct"].to_numpy(dtype=float)
    sq = ret ** 2
    n = len(ret)
    start = int(np.searchsorted(returns["date"].to_numpy(), first_origin_date))
    if start < INIT_RETURNS:
        raise ValueError("Not enough history before the first forecast origin")
    init_var = sq[:INIT_RETURNS].mean()
    forecasts = {f"f_garch_{h}": np.full(n, np.nan) for h in horizons}
    log = []
    params = None
    for refit_at in range(start, n, refit_every):
        omega, alpha, beta, converged = fitter(ret[: refit_at + 1])
        if converged or params is None:
            params = (omega, alpha, beta)
        log.append({"refit_origin": returns["date"].iloc[refit_at], "train_returns": refit_at + 1,
                    "omega": omega, "alpha": alpha, "beta": beta, "converged": converged,
                    "used_params": "new" if params == (omega, alpha, beta) else "previous"})
        stop = min(refit_at + refit_every, n)
        one = garch_one_step(sq[:stop], *params, init_var)[refit_at:stop]
        for h in horizons:
            forecasts[f"f_garch_{h}"][refit_at:stop] = multi_step_sum(one, *params, h)
    return pd.DataFrame(forecasts, index=returns.index), pd.DataFrame(log)
