import math
import pandas as pd
from forecast_utils import classify_band_outcome
from config import (CLAIMS_BACKTEST_WEEKS, CLAIMS_BAND, CLAIMS_FORECAST_WINDOW,
                    CLAIMS_RECENT_WINDOW, CLAIMS_SERIES, CLAIMS_SPREAD_WINDOW,
                    fred_csv_url)

URL = fred_csv_url(CLAIMS_SERIES)
WEEKS = CLAIMS_BACKTEST_WEEKS

df = pd.read_csv(URL, index_col=0, parse_dates=True, na_values=["."]).dropna()
df.columns = ["claims"]
df["forecast"] = df["claims"].rolling(CLAIMS_FORECAST_WINDOW).mean().shift(1)
df["error"] = df["claims"] - df["forecast"]

def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

rows = []
for i in range(len(df) - WEEKS, len(df)):
    past = df["error"].iloc[i - CLAIMS_SPREAD_WINDOW:i].dropna()  # only prior errors
    sd = 1.4826 * (past - past.median()).abs().median()
    f = df["forecast"].iloc[i]
    actual = df["claims"].iloc[i]

    p_above = 1 - phi(CLAIMS_BAND / sd)
    p_below = phi(-CLAIMS_BAND / sd)
    p_in = 1 - p_above - p_below

    out = classify_band_outcome(actual, f, CLAIMS_BAND)

    hit = {"above": 0, "inline": 0, "below": 0}
    hit[out] = 1
    brier = ((p_above - hit["above"]) ** 2
             + (p_in - hit["inline"]) ** 2
             + (p_below - hit["below"]) ** 2)
    rows.append({"week": df.index[i].date(), "p_above": p_above, "p_inline": p_in,
                 "p_below": p_below, "outcome": out, "brier": brier})

res = pd.DataFrame(rows)

print("Weeks tested:", len(res))
print("Model Brier (all weeks):   ", round(res["brier"].mean(), 3))
print(f"Model Brier (last {CLAIMS_RECENT_WINDOW} wks): ", round(res["brier"].iloc[-CLAIMS_RECENT_WINDOW:].mean(), 3))
print("Random guessing:            0.667")

# fairer baseline: constant odds equal to how often each outcome happened
freq = res["outcome"].value_counts(normalize=True)
base = 0
for o in ["above", "inline", "below"]:
    p = freq.get(o, 0)
    base += (p * ((p - 1) ** 2 + sum(freq.get(k, 0) ** 2 for k in ["above", "inline", "below"] if k != o)))
print("Constant-odds baseline:    ", round(base, 3), "(uses hindsight, so slightly flattering)")

print()
print("Calibration: average predicted odds vs how often it really happened")
for o in ["above", "inline", "below"]:
    print(f"  {o:7s} predicted {res['p_' + o].mean():.2f}   actual {freq.get(o, 0):.2f}")
