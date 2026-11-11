import pandas as pd

df = pd.read_csv("cpi_history.csv")
print("Months of data:", len(df))
if len(df) < 12:
    print("Warning: under 12 months, treat these numbers as very rough.")

for name, fc, ac in [("Core", "core_forecast", "core_actual"),
                     ("Headline", "head_forecast", "head_actual")]:
    err = (df[ac] - df[fc]).round(2)
    print()
    print(f"{name} CPI (actual minus consensus)")
    print("  Average miss (bias):  ", round(err.mean(), 3))
    print("  Typical size (SD):    ", round(err.std(), 3))
    print("  Exactly as expected:  ", f"{(err == 0).mean():.0%}")
    print("  Hotter than expected: ", f"{(err > 0).mean():.0%}")
    print("  Cooler than expected: ", f"{(err < 0).mean():.0%}")