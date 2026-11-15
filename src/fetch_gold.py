"""Download daily COMEX gold futures OHLCV and report basic quality checks."""

from datetime import datetime, timezone

import yfinance as yf

from config import (GOLD_HISTORY_FILE, GOLD_SOURCE_NAME, GOLD_START_DATE,
                    GOLD_YAHOO_TICKER, GOLD_SPIKE_THRESHOLD)
from gold_data import inspect_gold_data, normalize_yahoo_gold


def main():
    print(f"Downloading daily history for {GOLD_YAHOO_TICKER} from {GOLD_SOURCE_NAME}...")
    downloaded = yf.download(
        tickers=GOLD_YAHOO_TICKER,
        start=GOLD_START_DATE,
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
        ticker=GOLD_YAHOO_TICKER,
        source=GOLD_SOURCE_NAME,
        downloaded_at_utc=timestamp,
    )
    report = inspect_gold_data(data, spike_threshold=GOLD_SPIKE_THRESHOLD)
    if not report.valid:
        raise SystemExit("Gold data failed validation: " + "; ".join(report.errors))

    GOLD_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(GOLD_HISTORY_FILE, index=False)
    print(f"Saved {len(data):,} daily rows to {GOLD_HISTORY_FILE}")
    print(f"Date range: {data['date'].iloc[0]} to {data['date'].iloc[-1]}")
    print(f"Source: {GOLD_SOURCE_NAME}; ticker: {GOLD_YAHOO_TICKER}; downloaded at {timestamp}")

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


if __name__ == "__main__":
    main()
