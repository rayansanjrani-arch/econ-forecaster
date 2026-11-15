import pandas as pd
from config import (CLAIMS_BACKTEST_WEEKS, CLAIMS_FORECAST_WINDOW,
                    CLAIMS_RECENT_WINDOW, CLAIMS_SERIES, fred_csv_url)

URL = fred_csv_url(CLAIMS_SERIES)

df = pd.read_csv(URL, index_col=0, parse_dates=True, na_values=["."])
df.columns = ["claims"]
df = df.dropna()

# naive forecast: average of the previous 4 weeks
df["forecast"] = df["claims"].rolling(CLAIMS_FORECAST_WINDOW).mean().shift(1)
df["error"] = df["claims"] - df["forecast"]

recent = df["error"].dropna().iloc[-(CLAIMS_BACKTEST_WEEKS):]  # about 2 years of weeks
print("Weeks used:", len(recent))
print("Error spread (SD):", round(recent.std()))
print(f"Bias, last {CLAIMS_RECENT_WINDOW} weeks:", round(df["error"].dropna().iloc[-CLAIMS_RECENT_WINDOW:].mean()))
print()
print(df.tail(6).round(0))
print()
print("Naive forecast for next release:", round(df["claims"].iloc[-CLAIMS_FORECAST_WINDOW:].mean()))
