import pandas as pd

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=ICSA"

df = pd.read_csv(URL, index_col=0, parse_dates=True, na_values=["."])
df.columns = ["claims"]
df = df.dropna()

# naive forecast: average of the previous 4 weeks
df["forecast"] = df["claims"].rolling(4).mean().shift(1)
df["error"] = df["claims"] - df["forecast"]

recent = df["error"].dropna().iloc[-104:]  # about 2 years of weeks
print("Weeks used:", len(recent))
print("Error spread (SD):", round(recent.std()))
print("Bias, last 26 weeks:", round(df["error"].dropna().iloc[-26:].mean()))
print()
print(df.tail(6).round(0))
print()
print("Naive forecast for next release:", round(df["claims"].iloc[-4:].mean()))