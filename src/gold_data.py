"""Normalization and quality checks for daily Yahoo gold bars."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas.tseries.holiday import GoodFriday, USFederalHolidayCalendar


PRICE_COLUMNS = ("open", "high", "low", "close")
REQUIRED_COLUMNS = ("date", *PRICE_COLUMNS)


@dataclass
class GoldQualityReport:
    errors: list[str]
    missing_weekdays: list[str]
    unexpected_weekdays: list[str]
    large_moves: list[tuple[str, float]]

    @property
    def valid(self):
        return not self.errors


def normalize_yahoo_gold(data, ticker, source, downloaded_at_utc):
    """Flatten yfinance columns and keep source OHLCV values with provenance."""
    if data is None or data.empty:
        raise ValueError(f"Yahoo returned no daily data for {ticker}")

    field_names = {"open", "high", "low", "close", "volume"}
    columns = {}
    for column in data.columns:
        parts = column if isinstance(column, tuple) else (column,)
        field = next((str(part).strip().lower() for part in parts
                      if str(part).strip().lower() in field_names), None)
        if field:
            columns[field] = column

    missing = [field for field in PRICE_COLUMNS if field not in columns]
    if missing:
        raise ValueError(f"Yahoo data is missing required OHLC fields: {', '.join(missing)}")

    data = data.sort_index()
    normalized = pd.DataFrame(index=data.index)
    for field in (*PRICE_COLUMNS, "volume"):
        if field in columns:
            normalized[field] = pd.to_numeric(data[columns[field]], errors="coerce")
    if "volume" not in normalized:
        normalized["volume"] = np.nan
    normalized.index.name = "date"
    normalized = normalized.reset_index()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    normalized["ticker"] = ticker
    normalized["source"] = source
    normalized["downloaded_at_utc"] = downloaded_at_utc
    return normalized[["date", *PRICE_COLUMNS, "volume", "ticker", "source", "downloaded_at_utc"]]


def inspect_gold_data(frame, spike_threshold=0.05):
    """Check OHLC consistency and report candidate weekday gaps and large moves."""
    errors = []
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        return GoldQualityReport(
            errors=[f"Missing columns: {', '.join(missing_columns)}"],
            missing_weekdays=[], unexpected_weekdays=[], large_moves=[],
        )
    if frame.empty:
        return GoldQualityReport(
            errors=["Dataset is empty"], missing_weekdays=[], unexpected_weekdays=[], large_moves=[]
        )

    dates = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    if dates.isna().any():
        errors.append("One or more dates are missing or invalid")
    if dates.dropna().duplicated().any():
        errors.append("Duplicate trading dates found")

    prices = frame.loc[:, PRICE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(prices.to_numpy(dtype=float)).all():
        errors.append("OHLC values contain missing or non-finite prices")
    elif (prices <= 0).any().any():
        errors.append("OHLC prices must all be positive")
    else:
        invalid = (
            (prices["low"] > prices[["open", "close"]].min(axis=1))
            | (prices["high"] < prices[["open", "close"]].max(axis=1))
            | (prices["low"] > prices["high"])
        )
        if invalid.any():
            errors.append(f"Invalid OHLC ordering on {int(invalid.sum())} row(s)")

    valid_dates = dates.dropna()
    missing_weekdays = []
    unexpected_weekdays = []
    large_moves = []
    if not valid_dates.empty:
        observed = pd.DatetimeIndex(valid_dates.unique()).sort_values()
        expected_weekdays = pd.bdate_range(observed.min(), observed.max())
        missing_dates = expected_weekdays.difference(observed)
        missing_weekdays = [date.strftime("%Y-%m-%d") for date in missing_dates]
        federal_holidays = set(
            USFederalHolidayCalendar().holidays(observed.min(), observed.max()).normalize()
        )
        good_fridays = set(GoodFriday.dates(observed.min(), observed.max()).normalize())
        recognized_closures = federal_holidays | good_fridays
        unexpected_weekdays = [
            date.strftime("%Y-%m-%d") for date in missing_dates if date not in recognized_closures
        ]
        if unexpected_weekdays:
            errors.append(
                "Weekday gaps outside recognized U.S. federal holidays/Good Friday: "
                + ", ".join(unexpected_weekdays)
            )

        ordered = pd.DataFrame({"date": dates, "close": pd.to_numeric(frame["close"], errors="coerce")})
        ordered = ordered.dropna().sort_values("date")
        changes = ordered["close"].pct_change()
        for index in changes.index[changes.abs() > spike_threshold]:
            large_moves.append((ordered.loc[index, "date"].strftime("%Y-%m-%d"), float(changes.loc[index])))

    return GoldQualityReport(
        errors=errors,
        missing_weekdays=missing_weekdays,
        unexpected_weekdays=unexpected_weekdays,
        large_moves=large_moves,
    )
