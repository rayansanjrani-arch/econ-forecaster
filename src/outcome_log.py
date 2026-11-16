"""Append-only capture of first-reported economic outcomes."""

from pathlib import Path
import os

import pandas as pd

from config import FIRST_RELEASE_OUTCOMES_FILE, PREDICTIONS_FILE
from forecast_utils import classify_band_outcome, classify_cpi_outcome, round_half_up
from prediction_log import load_predictions


OUTCOME_COLUMNS = [
    "release", "indicator", "actual", "actual_secondary", "forecast",
    "forecast_secondary", "threshold", "outcome", "source", "source_url",
    "recorded_at_utc",
]


def load_outcomes(path=FIRST_RELEASE_OUTCOMES_FILE):
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=OUTCOME_COLUMNS)
    frame = pd.read_csv(path, keep_default_na=False)
    missing = [column for column in OUTCOME_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Outcome log is missing columns: {', '.join(missing)}")
    return frame[OUTCOME_COLUMNS]


def record_claims_outcome(release, actual, forecast, source, source_url,
                          prediction_path=PREDICTIONS_FILE,
                          outcome_path=FIRST_RELEASE_OUTCOMES_FILE, recorded_at_utc=None):
    return _record(
        release=release,
        indicator="initial_claims",
        actual=actual,
        forecast=forecast,
        threshold=3_000,
        outcome=classify_band_outcome(float(actual), float(forecast), 3_000),
        source=source,
        source_url=source_url,
        prediction_path=prediction_path,
        outcome_path=outcome_path,
        recorded_at_utc=recorded_at_utc,
    )


def record_cpi_outcome(release, core_actual, headline_actual, core_consensus,
                       headline_consensus, source, source_url,
                       prediction_path=PREDICTIONS_FILE,
                       outcome_path=FIRST_RELEASE_OUTCOMES_FILE, recorded_at_utc=None):
    return _record(
        release=release,
        indicator="core_cpi_mom",
        actual=core_actual,
        actual_secondary=headline_actual,
        forecast=core_consensus,
        forecast_secondary=headline_consensus,
        threshold=0,
        outcome=classify_cpi_outcome(
            round_half_up(core_actual, 1), round_half_up(core_consensus, 1),
            round_half_up(headline_actual, 1), round_half_up(headline_consensus, 1),
        ),
        source=source,
        source_url=source_url,
        prediction_path=prediction_path,
        outcome_path=outcome_path,
        recorded_at_utc=recorded_at_utc,
    )


def _record(release, indicator, actual, forecast, threshold, outcome, source, source_url,
            prediction_path, outcome_path, recorded_at_utc,
            actual_secondary="", forecast_secondary=""):
    release = pd.Timestamp(release).strftime("%Y-%m-%d")
    if not str(source).strip() or not str(source_url).strip():
        raise ValueError("A source name and source URL are required")
    numeric_values = [actual, forecast, threshold]
    if actual_secondary != "":
        numeric_values.append(actual_secondary)
    if forecast_secondary != "":
        numeric_values.append(forecast_secondary)
    if not all(pd.notna(float(value)) and abs(float(value)) != float("inf") for value in numeric_values):
        raise ValueError("Outcome values must be finite numbers")
    predictions = load_predictions(prediction_path)
    matching = predictions.loc[
        predictions["release"].astype(str).eq(release)
        & predictions["indicator"].astype(str).eq(indicator)
    ]
    if matching.empty:
        raise ValueError(f"No forecast exists for {indicator} on {release}")
    if matching.iloc[0]["outcome"]:
        raise ValueError("This prediction already has an outcome; the prediction log is immutable")
    outcome_path = Path(outcome_path)
    previous = load_outcomes(outcome_path)
    key = (release, indicator)
    if key in set(zip(previous["release"].astype(str), previous["indicator"].astype(str))):
        raise ValueError(f"A first-release outcome already exists for {indicator} on {release}")
    record = {
        "release": release,
        "indicator": indicator,
        "actual": float(actual),
        "actual_secondary": "" if actual_secondary == "" else float(actual_secondary),
        "forecast": float(forecast),
        "forecast_secondary": "" if forecast_secondary == "" else float(forecast_secondary),
        "threshold": float(threshold),
        "outcome": outcome,
        "source": str(source).strip(),
        "source_url": str(source_url).strip(),
        "recorded_at_utc": recorded_at_utc or pd.Timestamp.now(tz="UTC").isoformat(),
    }
    new_row = pd.DataFrame([record], columns=OUTCOME_COLUMNS)
    # Skip concat for an empty ledger: pandas is changing how empty frames affect dtypes.
    updated = new_row if previous.empty else pd.concat([previous, new_row], ignore_index=True)
    outcome_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = outcome_path.with_name(outcome_path.name + ".tmp")
    updated.to_csv(temp_path, index=False)
    os.replace(temp_path, outcome_path)
    return record


def completed_predictions(prediction_path=PREDICTIONS_FILE, outcome_path=FIRST_RELEASE_OUTCOMES_FILE):
    """Fill blank legacy outcome cells from the append-only first-release log."""
    predictions = load_predictions(prediction_path)
    outcomes = load_outcomes(outcome_path)
    if predictions.empty or outcomes.empty:
        return predictions
    result_by_key = {
        (str(row.release), str(row.indicator)): row.outcome
        for row in outcomes.itertuples(index=False)
    }
    for index, row in predictions.iterrows():
        key = (str(row["release"]), str(row["indicator"]))
        if not str(row["outcome"]).strip() and key in result_by_key:
            predictions.loc[index, "outcome"] = result_by_key[key]
    return predictions
