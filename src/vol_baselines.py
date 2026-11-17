"""Task 3.2: historical-volatility and EWMA variance forecasts (no fitted parameters)."""

import numpy as np
import pandas as pd

from vol_scoring import assign_window, mse, qlike, realized_variance

EWMA_LAMBDA = 0.94
EWMA_INIT_RETURNS = 60
BASELINES = ("hv20", "hv60", "ewma")


def baseline_forecasts(returns):
    """One-step variance forecasts made at each origin's close, using returns up to that origin."""
    sq = returns["ret_pct"].to_numpy(dtype=float) ** 2
    n = len(sq)
    out = {}
    for name, window in (("hv20", 20), ("hv60", 60)):
        f = np.full(n, np.nan)
        csum = np.concatenate([[0.0], np.cumsum(sq)])
        idx = np.arange(window - 1, n)
        f[idx] = (csum[idx + 1] - csum[idx + 1 - window]) / window
        out[name] = f
    ewma = np.full(n, np.nan)
    if n >= EWMA_INIT_RETURNS:
        var = sq[:EWMA_INIT_RETURNS].mean()  # state before using return at index INIT-1 below
        for t in range(EWMA_INIT_RETURNS - 1, n):
            var = EWMA_LAMBDA * var + (1 - EWMA_LAMBDA) * sq[t]
            ewma[t] = var
    out["ewma"] = ewma
    return pd.DataFrame(out, index=returns.index)


def score_baselines(returns, horizons=(1, 5)):
    """Per-origin table of targets, forecasts and losses for every baseline and horizon."""
    table = realized_variance(returns, horizons)
    table["window"] = assign_window(table["date"])
    one_step = baseline_forecasts(returns)
    for name in BASELINES:
        for h in horizons:
            table[f"f_{name}_{h}"] = one_step[name] * h
    usable = table[[f"f_{n}_{h}" for n in BASELINES for h in horizons]].notna().all(axis=1)
    for h in horizons:
        usable &= table[f"rv_{h}"].notna()
    table = table[usable].reset_index(drop=True)
    for name in BASELINES:
        for h in horizons:
            table[f"qlike_{name}_{h}"] = qlike(table[f"f_{name}_{h}"], table[f"rv_{h}"])
            table[f"mse_{name}_{h}"] = mse(table[f"f_{name}_{h}"], table[f"rv_{h}"])
    return table


def summarise(table, models=BASELINES, horizons=(1, 5)):
    scored = table[table["window"] != ""]
    rows = []
    for h in horizons:
        for name in models:
            for window, part in list(scored.groupby("window")) + [("all", scored)]:
                rows.append({"horizon": h, "model": name, "window": window, "n": len(part),
                             "qlike": part[f"qlike_{name}_{h}"].mean(), "mse": part[f"mse_{name}_{h}"].mean()})
    return pd.DataFrame(rows)


def best_baseline(summary, horizon):
    full = summary[(summary["horizon"] == horizon) & (summary["window"] == "all")]
    return full.sort_values("qlike").iloc[0]["model"]
