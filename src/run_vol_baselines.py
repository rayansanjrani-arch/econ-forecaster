"""Task 3.2: score 20-day, 60-day and EWMA variance baselines on the Layer 3 windows."""

import argparse

from config import GOLD_GLD_LONG_FILE, REPORTS_DIR
from vol_baselines import best_baseline, score_baselines, summarise
from vol_scoring import log_returns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=GOLD_GLD_LONG_FILE)
    parser.add_argument("--output-dir", default=REPORTS_DIR / "volatility")
    args = parser.parse_args()
    from pathlib import Path
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    table = score_baselines(log_returns(args.gold))
    summary = summarise(table)
    table.round(6).to_csv(out / "baseline_forecasts.csv", index=False)
    summary.round(6).to_csv(out / "baseline_scores.csv", index=False)
    print(f"Scored {int((table['window'] != '').sum())} origins ({table['date'].iloc[0]} to {table['date'].iloc[-1]} incl. burn-in)")
    for h in (1, 5):
        view = summary[summary["horizon"] == h].pivot(index="window", columns="model", values="qlike")
        print(f"\nMean QLIKE, h = {h} (lower is better)")
        print(view.round(4).to_string())
        print(f"Best baseline for h = {h}: {best_baseline(summary, h)}")
    print(f"\nWritten to {out}")


if __name__ == "__main__":
    main()
