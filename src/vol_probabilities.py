"""Task 3.5: next-session move-range probabilities from walk-forward GARCH(1,1).

Primary: filtered historical simulation (GARCH volatility x empirical |z| from
training data only). Secondary: normal returns. Baseline: expanding climatology.
"""

import math

import numpy as np
import pandas as pd

from config import MOVE_RANGE_EDGES_PCT, VOL_REFIT_EVERY
from vol_garch import INIT_RETURNS, garch_one_step

LOG_LOSS_FLOOR = 1e-6
RANGE_LABELS = ("lt_0.5", "0.5_1", "1_2", "ge_2")


def range_index(abs_returns, edges=MOVE_RANGE_EDGES_PCT):
    """0..len(edges): which declared range each absolute return falls in (right-open)."""
    return np.searchsorted(np.asarray(edges), np.asarray(abs_returns, dtype=float), side="right")


def probs_from_abs_sample(sorted_abs_z, sigma, edges=MOVE_RANGE_EDGES_PCT):
    """P(range) for |r| = |z| * sigma, using a sorted sample of |z|; one row per sigma."""
    sigma = np.asarray(sigma, dtype=float)[:, None]
    thresholds = np.asarray(edges)[None, :] / sigma                       # |z| cut-offs
    cdf = np.searchsorted(sorted_abs_z, thresholds, side="left") / len(sorted_abs_z)
    cdf = np.hstack([np.zeros((len(sigma), 1)), cdf, np.ones((len(sigma), 1))])
    return np.diff(cdf, axis=1)


def probs_normal(sigma, edges=MOVE_RANGE_EDGES_PCT):
    sigma = np.asarray(sigma, dtype=float)[:, None]
    x = np.asarray(edges)[None, :] / sigma
    cdf_abs = np.vectorize(lambda v: math.erf(v / math.sqrt(2)))(x)      # P(|z| < x)
    cdf = np.hstack([np.zeros((len(sigma), 1)), cdf_abs, np.ones((len(sigma), 1))])
    return np.diff(cdf, axis=1)


def climatology(returns, start, stop, edges=MOVE_RANGE_EDGES_PCT):
    """For origins start..stop-1: frequencies of each range among returns 0..origin."""
    idx = range_index(np.abs(returns["ret_pct"].to_numpy()), edges)
    counts = np.zeros((len(returns), len(edges) + 1))
    counts[np.arange(len(idx)), idx] = 1
    cum = np.cumsum(counts, axis=0)
    rows = cum[start:stop]
    return rows / rows.sum(axis=1, keepdims=True)


def brier(probs, outcome_idx):
    onehot = np.zeros_like(probs); onehot[np.arange(len(probs)), outcome_idx] = 1
    return ((probs - onehot) ** 2).sum(axis=1)


def log_loss(probs, outcome_idx):
    return -np.log(np.maximum(probs[np.arange(len(probs)), outcome_idx], LOG_LOSS_FLOOR))


def walk_forward_probabilities(returns, first_origin_date, fitter, refit_every=VOL_REFIT_EVERY):
    """Per-origin probabilities (FHS, normal, climatology) and the observed next-session range."""
    ret = returns["ret_pct"].to_numpy(dtype=float)
    sq = ret ** 2
    n = len(ret)
    start = int(np.searchsorted(returns["date"].to_numpy(), first_origin_date))
    init_var = sq[:INIT_RETURNS].mean()
    k = len(MOVE_RANGE_EDGES_PCT) + 1
    fhs = np.full((n, k), np.nan); nrm = np.full((n, k), np.nan); sigma_out = np.full(n, np.nan)
    params = None
    for refit_at in range(start, n - 1, refit_every):
        omega, alpha, beta, converged = fitter(ret[: refit_at + 1])
        if converged or params is None:
            params = (omega, alpha, beta)
        stop = min(refit_at + refit_every, n - 1)
        one = garch_one_step(sq[:stop], *params, init_var)          # one[t]: variance for t+1
        abs_z = np.sort(np.abs(ret[1:refit_at + 1]) / np.sqrt(one[:refit_at]))
        sigma = np.sqrt(one[refit_at:stop])
        fhs[refit_at:stop] = probs_from_abs_sample(abs_z, sigma)
        nrm[refit_at:stop] = probs_normal(sigma)
        sigma_out[refit_at:stop] = sigma
    clim = np.full((n, k), np.nan)
    clim[start:n - 1] = climatology(returns, start, n - 1)
    outcome = np.full(n, -1)
    outcome[:-1] = range_index(np.abs(ret[1:]))
    return {"fhs": fhs, "normal": nrm, "climatology": clim, "sigma": sigma_out, "outcome": outcome}


def calibration_table(probs, outcome_idx, bins=np.linspace(0, 1, 11)):
    rows = []
    for j, label in enumerate(RANGE_LABELS):
        p = probs[:, j]; o = (outcome_idx == j).astype(float)
        b = np.clip(np.digitize(p, bins[1:-1]), 0, len(bins) - 2)
        for i in range(len(bins) - 1):
            mask = b == i
            if mask.any():
                rows.append({"range": label, "prob_bin": f"{bins[i]:.1f}-{bins[i+1]:.1f}", "n": int(mask.sum()),
                             "mean_forecast": float(p[mask].mean()), "observed": float(o[mask].mean())})
    return pd.DataFrame(rows)
