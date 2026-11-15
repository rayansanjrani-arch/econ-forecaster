import math
import pandas as pd
from forecast_utils import classify_band_outcome
from config import (CLAIMS_BACKTEST_WEEKS, CLAIMS_BAND, CLAIMS_FORECAST_WINDOW,
                    CLAIMS_SERIES, CLAIMS_SPREAD_WINDOW, CLAIMS_RECENT_WINDOW,
                    fred_csv_url)

URL = fred_csv_url(CLAIMS_SERIES)
WEEKS = CLAIMS_BACKTEST_WEEKS

df = pd.read_csv(URL, index_col=0, parse_dates=True, na_values=["."]).dropna()
df.columns = ["claims"]
df["base"] = df["claims"].rolling(CLAIMS_FORECAST_WINDOW).mean().shift(1)
df["error"] = df["claims"] - df["base"]

def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def run(bias_weeks, shrink):
    scores = []
    for i in range(len(df) - WEEKS, len(df)):
        past = df["error"].iloc[i - CLAIMS_SPREAD_WINDOW:i].dropna()
        sd = 1.4826 * (past - past.median()).abs().median()

        shift = 0.0
        if bias_weeks > 0:
            shift = shrink * df["error"].iloc[i - bias_weeks:i].mean()

        base = df["base"].iloc[i]
        mu = base + shift
        actual = df["claims"].iloc[i]

        # outcome is always judged against the base forecast, as in the live log
        p_above = 1 - phi((base + CLAIMS_BAND - mu) / sd)
        p_below = phi((base - CLAIMS_BAND - mu) / sd)
        p_in = 1 - p_above - p_below

        out = classify_band_outcome(actual, base, CLAIMS_BAND)
        hit = {"above": 0, "inline": 0, "below": 0}
        hit[out] = 1
        scores.append((p_above - hit["above"]) ** 2
                      + (p_in - hit["inline"]) ** 2
                      + (p_below - hit["below"]) ** 2)
    s = pd.Series(scores)
    return s.mean(), s.iloc[-CLAIMS_RECENT_WINDOW:].mean()

print(f"variant                       all weeks   last {CLAIMS_RECENT_WINDOW}")
for name, bw, sh in [("v1: no adjustment", 0, 0),
                     ("8 wks, half shift", 8, 0.5),
                     ("13 wks, half shift", 13, 0.5),
                     ("26 wks, half shift", 26, 0.5),
                     ("13 wks, full shift", 13, 1.0)]:
    a, b = run(bw, sh)
    print(f"{name:28s}  {a:.3f}      {b:.3f}")
print("Random guessing: 0.667")
