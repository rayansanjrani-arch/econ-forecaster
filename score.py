import pandas as pd

df = pd.read_csv("predictions.csv")
done = df.dropna(subset=["outcome"]).copy()

def brier(row):
    actual = {"hot": 0, "inline": 0, "cool": 0}
    actual[row["outcome"]] = 1
    return ((row["p_hot"] - actual["hot"]) ** 2
            + (row["p_inline"] - actual["inline"]) ** 2
            + (row["p_cool"] - actual["cool"]) ** 2)

done["brier"] = done.apply(brier, axis=1)
print(done[["release", "indicator", "outcome", "brier"]])
print("Average Brier:", round(done["brier"].mean(), 3))
print("Random guessing scores 0.667. Lower is better.")