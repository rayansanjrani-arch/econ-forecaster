"""Score completed predictions and compare them with simple baselines."""

import sys

import pandas as pd

from forecast_utils import OUTCOMES, brier_score
from prediction_log import LOG_PATH, load_predictions


def add_scores(frame):
    """Add model, uniform-guessing, and prequential historical-prior scores."""
    done = frame.loc[frame["outcome"].astype(str).str.strip().ne("")].copy()
    if done.empty:
        return done

    def score_row(row):
        probabilities = {name: row[f"p_{name}"] for name in OUTCOMES}
        return brier_score(probabilities, row["outcome"])

    done["brier"] = done.apply(score_row, axis=1)
    done["uniform_baseline"] = done.apply(
        lambda row: brier_score({name: 1 / 3 for name in OUTCOMES}, row["outcome"]), axis=1
    )
    done = done.sort_values(["sample_type", "indicator", "made_on", "release"], kind="stable")
    prior_scores = []
    for _, group in done.groupby(["sample_type", "indicator"], sort=False):
        counts = {name: 0 for name in OUTCOMES}
        for _, row in group.iterrows():
            total = sum(counts.values())
            prior = (
                {name: counts[name] / total for name in OUTCOMES}
                if total else {name: 1 / 3 for name in OUTCOMES}
            )
            prior_scores.append((row.name, brier_score(prior, row["outcome"])))
            counts[row["outcome"]] += 1
    prior_score_map = dict(prior_scores)
    done["historical_prior_baseline"] = [prior_score_map[index] for index in done.index]
    return done


def calibration_table(done):
    """Summarize predicted probabilities against event frequencies by 0.2 bins."""
    rows = []
    edges = [0, 0.2, 0.4, 0.6, 0.8, 1.0000001]
    labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    for outcome in OUTCOMES:
        part = done[["sample_type", "indicator", "outcome", f"p_{outcome}"]].copy()
        part["probability_bin"] = pd.cut(part[f"p_{outcome}"], edges, labels=labels, right=False)
        part["occurred"] = part["outcome"].eq(outcome).astype(int)
        grouped = part.groupby(["sample_type", "indicator", "probability_bin"], observed=True)
        for (sample_type, indicator, probability_bin), values in grouped:
            rows.append({
                "sample_type": sample_type,
                "indicator": indicator,
                "outcome_class": outcome,
                "probability_bin": probability_bin,
                "n": len(values),
                "mean_predicted": values[f"p_{outcome}"].mean(),
                "observed_frequency": values["occurred"].mean(),
            })
    return pd.DataFrame(rows)


def main(path=LOG_PATH):
    predictions = load_predictions(path)
    if predictions.empty:
        print("No predictions in the log.")
        return
    done = add_scores(predictions)
    if done.empty:
        print("No completed predictions to score yet.")
        return

    print("Brier score by sample type and indicator (lower is better)")
    summary = done.groupby(["sample_type", "indicator"], as_index=False).agg(
        n=("brier", "size"),
        model_brier=("brier", "mean"),
        uniform_baseline=("uniform_baseline", "mean"),
        historical_prior_baseline=("historical_prior_baseline", "mean"),
    )
    print(summary.to_string(index=False, formatters={
        "model_brier": "{:.3f}".format,
        "uniform_baseline": "{:.3f}".format,
        "historical_prior_baseline": "{:.3f}".format,
    }))
    print("Uniform baseline: 0.667. Historical prior uses only earlier outcomes in the same group.")
    print("Backfilled results are diagnostic and are not live evidence.")

    print("\nCalibration (small samples are highly uncertain)")
    calibration = calibration_table(done)
    if calibration.empty:
        print("No calibration bins available.")
    else:
        print(calibration.to_string(index=False, formatters={
            "mean_predicted": "{:.3f}".format,
            "observed_frequency": "{:.3f}".format,
        }))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else LOG_PATH)
