import pandas as pd
from config import (CORE_CPI_SERIES, CPI_FORECAST_WINDOW, CPI_GAP_LIMIT_DAYS,
                    CPI_RECENT_BIAS_WINDOW, CPI_STATS_WINDOW, fred_csv_url)

URL = fred_csv_url(CORE_CPI_SERIES)

df = pd.read_csv(URL, index_col=0, parse_dates=True, na_values=["."])
df.columns = ["idx"]
df = df.dropna()

df["mom"] = df["idx"].pct_change() * 100

# the shutdown left a missing month, so skip any change that spans a gap
gap = df.index.to_series().diff().dt.days > CPI_GAP_LIMIT_DAYS
df.loc[gap, "mom"] = None

# naive forecast: average of the previous 3 months
df["forecast"] = df["mom"].rolling(CPI_FORECAST_WINDOW).mean().shift(1)
df["error"] = df["mom"] - df["forecast"]

recent = df["error"].dropna().iloc[-CPI_STATS_WINDOW:]
print("Months used:", len(recent))
print("Error spread (SD):", round(recent.std(), 3))
print(f"Bias, last {CPI_RECENT_BIAS_WINDOW} months:", round(df["error"].dropna().iloc[-CPI_RECENT_BIAS_WINDOW:].mean(), 3))
print()
print(df[["mom", "forecast", "error"]].tail(6).round(3))
