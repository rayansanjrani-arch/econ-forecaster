"""Task 1.1a: compare GC=F futures with the GLD ETF cross-check, day by day."""

import argparse

import pandas as pd

from config import GOLD_CROSSCHECK_FILE, GOLD_HISTORY_FILE, GOLD_SOURCE_CHECK_FILE, GOLD_SOURCE_DIFF_FLAG_PCT
from gold_source_check import compare_gold_sources, save_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", default=GOLD_HISTORY_FILE)
    parser.add_argument("--secondary", default=GOLD_CROSSCHECK_FILE)
    parser.add_argument("--output", default=GOLD_SOURCE_CHECK_FILE)
    args = parser.parse_args()
    try:
        daily, by_period, coverage = compare_gold_sources(args.primary, args.secondary)
        path = save_check(daily, args.output)
    except (OSError, ValueError) as exc:
        parser.error(f"{exc}. Download the cross-check first: python src/fetch_gold.py --crosscheck")
    print(f"Compared {coverage['primary_ticker']} ({coverage['primary_rows']} rows) with "
          f"{coverage['secondary_ticker']} ({coverage['secondary_rows']} rows) on {coverage['common_dates']} common dates")
    for side in ("only_primary", "only_secondary"):
        dates = coverage[side]
        print(f"Dates {side.replace('_', ' in ')}: {len(dates)}" + (f" -> {', '.join(dates[:15])}" + (" ..." if len(dates) > 15 else "") if dates else ""))
    print("\nAgreement by period (returns on common dates only; closing times differ):")
    print(by_period.round(3).to_string(index=False))
    flagged = daily[daily["flag_large_difference"]]
    print(f"\nDays with daily returns differing by more than {GOLD_SOURCE_DIFF_FLAG_PCT} points: {len(flagged)} (review, not removed)")
    if len(flagged):
        print(flagged[["date", "primary_return_pct", "secondary_return_pct", "return_difference_pct"]].round(2).to_string(index=False))
    print(f"\nDaily comparison written to {path}")


if __name__ == "__main__":
    main()
