import sys
import math
import pandas as pd

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=ICSA"
BAND = 3000  # within +/-3,000 of the forecast counts as "in line"

df = pd.read_csv(URL, index_col=0, parse_dates=True, na_values=["."]).dropna()
df.columns = ["claims"]

df["forecast"] = df["claims"].rolling(4).mean().shift(1)
df["error"] = df["claims"] - df["forecast"]

# robust spread: median absolute deviation, ignores outlier weeks
errs = df["error"].dropna().iloc[-52:]
sd = 1.4826 * (errs - errs.median()).abs().median()

# forecast: use a real consensus if you pass one, else the 4-week average
if len(sys.argv) > 1:
    forecast = float(sys.argv[1])
    source = "consensus"
else:
    forecast = df["claims"].iloc[-4:].mean()
    source = "4-week average"

def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

p_above = 1 - phi(BAND / sd)
p_below = phi(-BAND / sd)
p_inline = 1 - p_above - p_below

last_obs = df.index[-1]
release = (last_obs + pd.Timedelta(days=12)).date()  # Saturday week-end -> following Thursday

print(f"Forecast ({source}): {forecast:,.0f}   spread (robust SD): {sd:,.0f}")
print(f"Release date: {release}")
print(f"P(above): {p_above:.2f}   P(in line): {p_inline:.2f}   P(below): {p_below:.2f}")

row = pd.DataFrame([{
    "release": release,
    "indicator": "initial_claims",
    "made_on": pd.Timestamp.today().date(),
    "p_above": round(p_above, 3),
    "p_inline": round(p_inline, 3),
    "p_below": round(p_below, 3),
    "outcome": "",
    "note": f"forecast {forecast:,.0f} ({source}), band +/-{BAND}",
}])
log = pd.read_csv("predictions.csv")
pd.concat([log, row]).to_csv("predictions.csv", index=False)
print("Saved to predictions.csv")