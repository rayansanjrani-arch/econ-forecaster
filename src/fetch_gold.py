"""Download daily gold OHLCV from Yahoo and report basic quality checks.

Default: COMEX gold futures (GC=F), the primary series. With --crosscheck:
the GLD gold ETF, saved separately as an independent cross-check (Task 1.1a).
"""

import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import yfinance as yf

from config import (GLD_LONG_START, GOLD_CROSSCHECK_FILE, GOLD_CROSSCHECK_TICKER, GOLD_GLD_LONG_FILE, GOLD_HISTORY_FILE,
                    GOLD_SOURCE_NAME, GOLD_SPIKE_THRESHOLD, GOLD_START_DATE,
                    GOLD_YAHOO_TICKER, NYSE_EXTRA_CLOSURES)
from gold_data import drop_incomplete_sessions, inspect_gold_data, normalize_yahoo_gold


def download(ticker, path, extra_closures=(), start=GOLD_START_DATE):
    print(f"Downloading daily history for {ticker} from {GOLD_SOURCE_NAME}...")
    downloaded = yf.download(
        tickers=ticker,
        start=start,
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
        timeout=30,
        multi_level_index=False,
    )
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    data = normalize_yahoo_gold(
        downloaded,
        ticker=ticker,
        source=GOLD_SOURCE_NAME,
        downloaded_at_utc=timestamp,
    )
    today_new_york = datetime.now(ZoneInfo("America/New_York")).date()
    data, dropped = drop_incomplete_sessions(data, today_new_york)
    if dropped:
        print(f"Skipped possibly incomplete current-day bar(s): {', '.join(dropped)}")
    report = inspect_gold_data(data, spike_threshold=GOLD_SPIKE_THRESHOLD, extra_closures=extra_closures)
    if not report.valid:
        raise SystemExit("Gold data failed validation: " + "; ".join(report.errors))

    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(path, index=False)
    print(f"Saved {len(data):,} daily rows to {path}")
    print(f"Date range: {data['date'].iloc[0]} to {data['date'].iloc[-1]}")
    print(f"Source: {GOLD_SOURCE_NAME}; ticker: {ticker}; downloaded at {timestamp}")

    if report.missing_weekdays:
        sample = ", ".join(report.missing_weekdays[:20])
        suffix = " ..." if len(report.missing_weekdays) > 20 else ""
        print(
            f"{len(report.missing_weekdays)} weekdays have no bar; holidays/closures account for "
            f"{len(report.missing_weekdays) - len(report.unexpected_weekdays)}. "
            f"Examples: {sample}{suffix}"
        )
    else:
        print("No missing weekdays found.")

    if report.large_moves:
        details = ", ".join(f"{date} ({change:+.1%})" for date, change in report.large_moves)
        print(
            f"Review {len(report.large_moves)} close-to-close moves above "
            f"{GOLD_SPIKE_THRESHOLD:.0%}; market moves and futures rolls can both cause these: {details}"
        )
    else:
        print(f"No close-to-close moves above {GOLD_SPIKE_THRESHOLD:.0%} found.")

    if report.unexpected_weekdays:
        print("Unexplained weekday gaps need review: " + ", ".join(report.unexpected_weekdays))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosscheck", action="store_true",
                        help=f"download the {GOLD_CROSSCHECK_TICKER} ETF cross-check instead of {GOLD_YAHOO_TICKER}")
    parser.add_argument("--long-history", action="store_true",
                        help=f"download {GOLD_CROSSCHECK_TICKER} from {GLD_LONG_START} to a separate file (replication)")
    args = parser.parse_args()
    if args.long_history:
        download(GOLD_CROSSCHECK_TICKER, GOLD_GLD_LONG_FILE, extra_closures=tuple(NYSE_EXTRA_CLOSURES), start=GLD_LONG_START)
    elif args.crosscheck:
        download(GOLD_CROSSCHECK_TICKER, GOLD_CROSSCHECK_FILE, extra_closures=tuple(NYSE_EXTRA_CLOSURES))
    else:
        download(GOLD_YAHOO_TICKER, GOLD_HISTORY_FILE)


if __name__ == "__main__":
    main()
