import sys
import math
import pandas as pd
from prediction_log import append_prediction
from config import (CLAIMS_BAND, CLAIMS_FORECAST_WINDOW, CLAIMS_SERIES,
                    CLAIMS_SPREAD_WINDOW, PREDICTIONS_FILE, fred_csv_url)

URL = fred_csv_url(CLAIMS_SERIES)

df = pd.read_csv(URL, index_col=0, parse_dates=True, na_values=["."]).dropna()
df.columns = ["claims"]

df["forecast"] = df["claims"].rolling(CLAIMS_FORECAST_WINDOW).mean().shift(1)
df["error"] = df["claims"] - df["forecast"]

# robust spread: median absolute deviation, ignores outlier weeks
errs = df["error"].dropna().iloc[-CLAIMS_SPREAD_WINDOW:]
sd = 1.4826 * (errs - errs.median()).abs().median()

# forecast: use a real consensus if you pass one, else the 4-week average
if len(sys.argv) > 1:
    forecast = float(sys.argv[1])
    source = "consensus"
else:
    forecast = df["claims"].iloc[-CLAIMS_FORECAST_WINDOW:].mean()
    source = "4-week average"

def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

p_above = 1 - phi(CLAIMS_BAND / sd)
p_below = phi(-CLAIMS_BAND / sd)
p_inline = 1 - p_above - p_below

last_obs = df.index[-1]
release = (last_obs + pd.Timedelta(days=12)).date()  # next weekly claims release; verify holiday weeks

print(f"Forecast ({source}): {forecast:,.0f}   spread (robust SD): {sd:,.0f}")
print(f"Release date: {release}")
print(f"P(above): {p_above:.2f}   P(in line): {p_inline:.2f}   P(below): {p_below:.2f}")

row = {
    "release": release,
    "indicator": "initial_claims",
    "made_on": pd.Timestamp.today().date(),
    "p_above": round(p_above, 3),
    "p_inline": round(p_inline, 3),
    "p_below": round(p_below, 3),
    "outcome": "",
    "note": f"forecast {forecast:,.0f} ({source}), band +/-{CLAIMS_BAND}",
}
append_prediction(row)
print(f"Saved to {PREDICTIONS_FILE}")
