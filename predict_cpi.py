import sys
import numpy as np
import pandas as pd

if len(sys.argv) < 4:
    sys.exit("Usage: python predict_cpi.py CORE_FC HEADLINE_FC RELEASE_DATE [save]")
core_fc = float(sys.argv[1])
head_fc = float(sys.argv[2])
release = sys.argv[3]
save = len(sys.argv) > 4 and sys.argv[4] == "save"

def load(series):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    df = pd.read_csv(url, index_col=0, parse_dates=True, na_values=["."]).dropna()
    df.columns = ["idx"]
    df["mom"] = df["idx"].pct_change() * 100
    gap = df.index.to_series().diff().dt.days > 40   # skip changes spanning the shutdown gap
    df.loc[gap, "mom"] = None
    df["error"] = df["mom"] - df["mom"].rolling(3).mean().shift(1)
    return df

def robust_sd(df, n=36):
    e = df["error"].dropna().iloc[-n:]
    return 1.4826 * (e - e.median()).abs().median()

core_sd = robust_sd(load("CPILFESL"))
head_sd = robust_sd(load("CPIAUCSL"))

def r1(x):                      # round half up to one decimal, like published figures
    return float(np.floor(x * 10 + 0.5) / 10)

cons_core, cons_head = r1(core_fc), r1(head_fc)

rng = np.random.default_rng(42)
N = 200000
core = np.floor(rng.normal(core_fc, core_sd, N) * 10 + 0.5) / 10
head = np.floor(rng.normal(head_fc, head_sd, N) * 10 + 0.5) / 10

above = (core > cons_core) | ((core == cons_core) & (head > cons_head))
below = (core < cons_core) | ((core == cons_core) & (head < cons_head))
inline = ~above & ~below

print(f"Core forecast {core_fc} (published {cons_core}), spread {core_sd:.3f}")
print(f"Headline forecast {head_fc} (published {cons_head}), spread {head_sd:.3f}")
print(f"P(above): {above.mean():.2f}   P(in line): {inline.mean():.2f}   P(below): {below.mean():.2f}")

if save:
    row = pd.DataFrame([{
        "release": release, "indicator": "core_cpi_mom",
        "made_on": pd.Timestamp.today().date(),
        "p_above": round(above.mean(), 3), "p_inline": round(inline.mean(), 3),
        "p_below": round(below.mean(), 3), "outcome": "",
        "note": f"core fc {core_fc}, head fc {head_fc}, sd {core_sd:.3f}/{head_sd:.3f}",
    }])
    log = pd.read_csv("predictions.csv")
    pd.concat([log, row]).to_csv("predictions.csv", index=False)
    print("Saved to predictions.csv")
else:
    print("(dry run, nothing saved. Add 'save' as a fourth argument to log it.)")