import pandas as pd

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPILFESL"

df = pd.read_csv(URL, index_col=0, parse_dates=True, na_values=["."])
df.columns = ["idx"]
df = df.dropna()

df["mom"] = df["idx"].pct_change() * 100

# the shutdown left a missing month, so skip any change that spans a gap
gap = df.index.to_series().diff().dt.days > 40
df.loc[gap, "mom"] = None

# naive forecast: average of the previous 3 months
df["forecast"] = df["mom"].rolling(3).mean().shift(1)
df["error"] = df["mom"] - df["forecast"]

recent = df["error"].dropna().iloc[-60:]
print("Months used:", len(recent))
print("Error spread (SD):", round(recent.std(), 3))
print("Bias, last 12 months:", round(df["error"].dropna().iloc[-12:].mean(), 3))
print()
print(df[["mom", "forecast", "error"]].tail(6).round(3))