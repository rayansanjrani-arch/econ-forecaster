"""Task 3.1: targets, losses, windows and the keep rule for volatility forecasts.

Declared in EXPERIMENTS.md (2026-11-17) before any model was fitted. A forecast
made at the close of session t is a variance (percent squared) for the next h
sessions; the target is the realized variance over those sessions.
"""

import numpy as np
import pandas as pd

from config import (VOL_BOOTSTRAP_BLOCK, VOL_BOOTSTRAP_RESAMPLES, VOL_BOOTSTRAP_SEED,
                    VOL_HORIZONS, VOL_KEEP_MIN_WINDOWS, VOL_WINDOWS)


def log_returns(gold_path):
    """Close-to-close log returns in percent between observed sessions."""
    gold = pd.read_csv(gold_path, dtype={"date": str})
    close = pd.to_numeric(gold["close"], errors="coerce")
    if gold["date"].duplicated().any() or close.isna().any() or (close <= 0).any():
        raise ValueError("Gold history needs unique dates and positive closes")
    order = np.argsort(gold["date"].to_numpy())
    dates = gold["date"].to_numpy()[order]
    close = close.to_numpy()[order]
    ret = np.log(close[1:] / close[:-1]) * 100
    return pd.DataFrame({"date": dates[1:], "ret_pct": ret})


def realized_variance(returns, horizons=VOL_HORIZONS):
    """Add rv_h columns: sum of the next h squared returns after each origin (NaN if incomplete)."""
    out = returns.copy()
    sq = out["ret_pct"].to_numpy() ** 2
    n = len(sq)
    for h in horizons:
        rv = np.full(n, np.nan)
        csum = np.concatenate([[0.0], np.cumsum(sq)])
        idx = np.arange(n - h)
        rv[idx] = csum[idx + 1 + h] - csum[idx + 1]
        out[f"rv_{h}"] = rv
    return out


def qlike(forecast, realized):
    """QLIKE loss log(F) + RV/F; requires positive forecasts; defined for RV = 0."""
    forecast = np.asarray(forecast, dtype=float)
    realized = np.asarray(realized, dtype=float)
    if (forecast <= 0).any() or np.isnan(forecast).any():
        raise ValueError("QLIKE needs positive, non-missing variance forecasts")
    return np.log(forecast) + realized / forecast


def mse(forecast, realized):
    return (np.asarray(forecast, dtype=float) - np.asarray(realized, dtype=float)) ** 2


def assign_window(dates, windows=VOL_WINDOWS):
    """Label each origin date with its evaluation window; '' means burn-in (not scored)."""
    dates = pd.to_datetime(pd.Series(dates))
    labels = pd.Series("", index=dates.index, dtype=object)
    for name, start, end in windows:
        labels[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))] = name
    return labels.to_numpy()


def moving_block_bootstrap_ci(values, block=VOL_BOOTSTRAP_BLOCK, resamples=VOL_BOOTSTRAP_RESAMPLES,
                              seed=VOL_BOOTSTRAP_SEED, level=0.95):
    """Percentile interval for the mean of a time-ordered series, resampling contiguous blocks."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < block:
        raise ValueError("Series shorter than the bootstrap block length")
    rng = np.random.default_rng(seed)
    starts_needed = int(np.ceil(n / block))
    offsets = np.arange(block)
    means = np.empty(resamples)
    for i in range(resamples):
        starts = rng.integers(0, n - block + 1, size=starts_needed)
        means[i] = values[(starts[:, None] + offsets).ravel()[:n]].mean()
    alpha = (1 - level) / 2
    return float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha))


def keep_decision(frame, candidate_col, baseline_col, window_col="window",
                  min_windows=VOL_KEEP_MIN_WINDOWS, **bootstrap):
    """Apply the declared keep rule to per-forecast losses (lower is better).

    Kept only if the candidate's mean loss beats the baseline in at least
    `min_windows` windows and the block-bootstrap interval of the full-period
    mean difference (candidate - baseline) lies entirely below 0.
    """
    scored = frame[frame[window_col] != ""].dropna(subset=[candidate_col, baseline_col])
    by_window = scored.groupby(window_col)[[candidate_col, baseline_col]].mean()
    by_window["candidate_better"] = by_window[candidate_col] < by_window[baseline_col]
    diff = (scored[candidate_col] - scored[baseline_col]).to_numpy()
    low, high = moving_block_bootstrap_ci(diff, **bootstrap)
    windows_won = int(by_window["candidate_better"].sum())
    return {
        "windows_won": windows_won, "windows_total": len(by_window),
        "mean_difference": float(diff.mean()), "ci_low": low, "ci_high": high,
        "keep": windows_won >= min_windows and high < 0,
        "by_window": by_window,
    }
