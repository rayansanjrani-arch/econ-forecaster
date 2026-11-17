"""Task 3.3: walk-forward GARCH(1,1) scored against the EWMA baseline."""

import argparse
from pathlib import Path

import pandas as pd

from config import GOLD_GLD_LONG_FILE, REPORTS_DIR, VOL_WINDOWS
from vol_baselines import score_baselines
from vol_garch import walk_forward_garch
from vol_scoring import keep_decision, log_returns, mse, qlike


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=GOLD_GLD_LONG_FILE)
    parser.add_argument("--output-dir", default=REPORTS_DIR / "volatility")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    returns = log_returns(args.gold)
    first_origin = VOL_WINDOWS[0][1]
    garch, fit_log = walk_forward_garch(returns, first_origin)
    table = score_baselines(returns)
    table = table.merge(pd.concat([returns[["date"]], garch], axis=1), on="date", how="left")
    table = table[table["window"] != ""].reset_index(drop=True)
    if table[["f_garch_1", "f_garch_5"]].isna().any().any():
        raise SystemExit("Missing GARCH forecasts inside the scored windows")
    for h in (1, 5):
        table[f"qlike_garch_{h}"] = qlike(table[f"f_garch_{h}"], table[f"rv_{h}"])
        table[f"mse_garch_{h}"] = mse(table[f"f_garch_{h}"], table[f"rv_{h}"])
    table.round(6).to_csv(out / "garch_forecasts.csv", index=False)
    fit_log.to_csv(out / "garch_fit_log.csv", index=False)

    print(f"GARCH refits: {len(fit_log)}; not converged: {int((~fit_log['converged']).sum())}")
    last = fit_log.iloc[-1]
    print(f"Latest parameters: omega {last.omega:.4f}, alpha {last.alpha:.4f}, beta {last.beta:.4f} "
          f"(alpha+beta {last.alpha + last.beta:.4f})")
    print(f"Parameter ranges: alpha {fit_log.alpha.min():.3f}-{fit_log.alpha.max():.3f}, "
          f"beta {fit_log.beta.min():.3f}-{fit_log.beta.max():.3f}")
    rows = []
    for h in (1, 5):
        d = keep_decision(table, f"qlike_garch_{h}", f"qlike_ewma_{h}")
        bw = d["by_window"].rename(columns={f"qlike_garch_{h}": "garch", f"qlike_ewma_{h}": "ewma"})
        print(f"\nh = {h}: mean QLIKE by window (lower is better)")
        print(bw.round(4).to_string())
        print(f"GARCH minus EWMA, full period: {d['mean_difference']:.4f} [{d['ci_low']:.4f}, {d['ci_high']:.4f}]; "
              f"windows won {d['windows_won']}/{d['windows_total']} -> {'KEEP' if d['keep'] else 'NOT KEPT'}")
        print(f"MSE full period: GARCH {table[f'mse_garch_{h}'].mean():.3f} vs EWMA {table[f'mse_ewma_{h}'].mean():.3f}")
        rows.append({"horizon": h, "windows_won": d["windows_won"], "mean_difference": d["mean_difference"],
                     "ci_low": d["ci_low"], "ci_high": d["ci_high"], "keep": d["keep"]})
    pd.DataFrame(rows).round(6).to_csv(out / "garch_vs_ewma.csv", index=False)
    print(f"\nWritten to {out}")


if __name__ == "__main__":
    main()
