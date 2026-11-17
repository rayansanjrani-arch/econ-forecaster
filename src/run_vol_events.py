"""Task 3.4: GARCH(1,1) with a pooled release-session adjustment, scored against GARCH."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config import (GOLD_GLD_LONG_FILE, RELEASE_CALENDAR_FILE, REPLICATION_CALENDAR_FILE,
                    REPORTS_DIR, VOL_WINDOWS)
from vol_events import params_from_log, release_session_flags, walk_forward_event_garch
from vol_scoring import assign_window, keep_decision, log_returns, mse, qlike, realized_variance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=GOLD_GLD_LONG_FILE)
    parser.add_argument("--output-dir", default=REPORTS_DIR / "volatility")
    args = parser.parse_args()
    out = Path(args.output_dir)
    returns = log_returns(args.gold)
    flags = release_session_flags(returns["date"], [REPLICATION_CALENDAR_FILE, RELEASE_CALENDAR_FILE])
    fit_log = pd.read_csv(out / "garch_fit_log.csv")
    forecasts, delta_log = walk_forward_event_garch(returns, flags, VOL_WINDOWS[0][1], params_from_log(fit_log))

    table = realized_variance(returns)
    table["window"] = assign_window(table["date"])
    table["release_next"] = np.append(flags[1:], False)
    table = pd.concat([table, forecasts], axis=1)
    table = table[(table["window"] != "") & table["rv_5"].notna()].reset_index(drop=True)

    previous = pd.read_csv(out / "garch_forecasts.csv", dtype={"date": str})
    check = table.merge(previous[["date", "f_garch_1", "f_garch_5"]], on="date", suffixes=("", "_task33"))
    gap = max((check["f_garch_1"] - check["f_garch_1_task33"]).abs().max(),
              (check["f_garch_5"] - check["f_garch_5_task33"]).abs().max())
    if len(check) != len(previous) or gap > 1e-5:
        raise SystemExit(f"Base GARCH forecasts do not reproduce Task 3.3 (rows {len(check)} vs {len(previous)}, max gap {gap})")
    print(f"Base GARCH reproduces Task 3.3 on {len(check)} origins (max difference {gap:.1e})")
    print(f"Release sessions flagged 2005-2026: {int(flags.sum())}; in scored windows next-session releases: {int(table['release_next'].sum())}")
    print(f"delta (re-estimated at each refit): first {delta_log.delta.iloc[0]:.3f}, last {delta_log.delta.iloc[-1]:.3f}, "
          f"range {delta_log.delta.min():.3f} to {delta_log.delta.max():.3f}")

    rows = []
    for h in (1, 5):
        for name in ("garch", "garchev"):
            table[f"qlike_{name}_{h}"] = qlike(table[f"f_{name}_{h}"], table[f"rv_{h}"])
            table[f"mse_{name}_{h}"] = mse(table[f"f_{name}_{h}"], table[f"rv_{h}"])
        d = keep_decision(table, f"qlike_garchev_{h}", f"qlike_garch_{h}")
        bw = d["by_window"].rename(columns={f"qlike_garchev_{h}": "garch+release", f"qlike_garch_{h}": "garch"})
        print(f"\nh = {h}: mean QLIKE by window (lower is better)")
        print(bw.round(4).to_string())
        print(f"GARCH+release minus GARCH: {d['mean_difference']:.4f} [{d['ci_low']:.4f}, {d['ci_high']:.4f}]; "
              f"windows won {d['windows_won']}/{d['windows_total']} -> {'KEEP' if d['keep'] else 'NOT KEPT'}")
        if h == 1:
            for flag, label in ((True, "next session is a release"), (False, "next session is not a release")):
                part = table[table["release_next"] == flag]
                print(f"  {label}: n={len(part)}, QLIKE garch {part['qlike_garch_1'].mean():.4f} vs +release {part['qlike_garchev_1'].mean():.4f}")
        rows.append({"horizon": h, "windows_won": d["windows_won"], "mean_difference": d["mean_difference"],
                     "ci_low": d["ci_low"], "ci_high": d["ci_high"], "keep": d["keep"]})
    pd.DataFrame(rows).round(6).to_csv(out / "garch_release_vs_garch.csv", index=False)
    delta_log.round(6).to_csv(out / "garch_release_delta_log.csv", index=False)
    table.round(6).to_csv(out / "garch_release_forecasts.csv", index=False)
    print(f"\nWritten to {out}")


if __name__ == "__main__":
    main()
