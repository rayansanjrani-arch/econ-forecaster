"""Task 3.5: score GARCH move-range probabilities against climatology; report calibration."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config import GOLD_GLD_LONG_FILE, REPORTS_DIR, VOL_WINDOWS
from vol_events import params_from_log
from vol_probabilities import RANGE_LABELS, brier, calibration_table, log_loss, walk_forward_probabilities
from vol_scoring import assign_window, keep_decision, log_returns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=GOLD_GLD_LONG_FILE)
    parser.add_argument("--output-dir", default=REPORTS_DIR / "volatility")
    args = parser.parse_args()
    out = Path(args.output_dir)
    returns = log_returns(args.gold)
    fit_log = pd.read_csv(out / "garch_fit_log.csv")
    res = walk_forward_probabilities(returns, VOL_WINDOWS[0][1], params_from_log(fit_log))

    table = pd.DataFrame({"date": returns["date"], "window": assign_window(returns["date"]),
                          "sigma": res["sigma"], "outcome": res["outcome"]})
    valid = (table["window"] != "") & (table["outcome"] >= 0) & ~np.isnan(res["fhs"]).any(axis=1)
    models = ("fhs", "normal", "climatology")
    for m in models:
        p = res[m]
        for j, label in enumerate(RANGE_LABELS):
            table[f"p_{m}_{label}"] = p[:, j]
    table = table[valid].reset_index(drop=True)
    outcome = table["outcome"].to_numpy()
    for m in models:
        p = table[[f"p_{m}_{l}" for l in RANGE_LABELS]].to_numpy()
        if not np.allclose(p.sum(axis=1), 1):
            raise SystemExit(f"{m} probabilities do not sum to 1")
        table[f"brier_{m}"] = brier(p, outcome)
        table[f"logloss_{m}"] = log_loss(p, outcome)

    print(f"Scored origins: {len(table)} ({table['date'].iloc[0]} to {table['date'].iloc[-1]})")
    print("Observed share of next-session ranges:",
          {l: round(float((outcome == j).mean()), 3) for j, l in enumerate(RANGE_LABELS)})
    scores = table.groupby("window")[[f"brier_{m}" for m in models] + [f"logloss_{m}" for m in models]].mean()
    scores.loc["all"] = table[[f"brier_{m}" for m in models] + [f"logloss_{m}" for m in models]].mean()
    print("\nMean scores by window (lower is better)")
    print(scores.round(4).to_string())
    rows = []
    for cand in ("fhs", "normal"):
        for score in ("brier", "logloss"):
            d = keep_decision(table, f"{score}_{cand}", f"{score}_climatology")
            rows.append({"candidate": cand, "score": score, "windows_won": d["windows_won"],
                         "mean_difference": d["mean_difference"], "ci_low": d["ci_low"], "ci_high": d["ci_high"],
                         "keep": d["keep"], "primary": cand == "fhs" and score == "brier"})
    decision = pd.DataFrame(rows)
    print("\nAgainst climatology (primary test: fhs, brier)")
    print(decision.round(4).to_string(index=False))

    print("\nCalibration: mean forecast vs observed share per range, full period")
    for m in models:
        p = table[[f"p_{m}_{l}" for l in RANGE_LABELS]].to_numpy()
        print(f"  {m:12s}", {l: f"{p[:, j].mean():.3f}/{(outcome == j).mean():.3f}" for j, l in enumerate(RANGE_LABELS)})
    p_fhs = table[[f"p_fhs_{l}" for l in RANGE_LABELS]].to_numpy()
    calib = calibration_table(p_fhs, outcome)
    print("\nFHS reliability (bins with n >= 50)")
    print(calib[calib.n >= 50].round(3).to_string(index=False))

    table.round(6).to_csv(out / "move_range_probabilities.csv", index=False)
    decision.round(6).to_csv(out / "move_range_vs_climatology.csv", index=False)
    calib.round(6).to_csv(out / "move_range_calibration_fhs.csv", index=False)
    print(f"\nWritten to {out}")


if __name__ == "__main__":
    main()
