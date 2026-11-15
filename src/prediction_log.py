"""Validated access to predictions.csv."""

from pathlib import Path
import math
import os

import pandas as pd
from config import PREDICTIONS_FILE


LOG_PATH = PREDICTIONS_FILE
SAMPLE_TYPES = ("live", "backfilled")
LOG_COLUMNS = [
    "release", "indicator", "made_on", "p_above", "p_inline", "p_below",
    "outcome", "note", "sample_type",
]


def _legacy_sample_type(note):
    return "backfilled" if "backfill" in str(note).casefold() else "live"


def load_predictions(path=LOG_PATH):
    """Load the log, classifying legacy rows from their existing note text."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=LOG_COLUMNS)
    frame = pd.read_csv(path, keep_default_na=False)
    for column in LOG_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    missing_type = frame["sample_type"].astype(str).str.strip().eq("")
    frame.loc[missing_type, "sample_type"] = frame.loc[missing_type, "note"].map(_legacy_sample_type)
    return frame[LOG_COLUMNS]


def _validate_row(row):
    missing = [name for name in LOG_COLUMNS[:-1] if name not in row]
    if missing:
        raise ValueError(f"Prediction is missing required fields: {', '.join(missing)}")
    if not str(row["release"]).strip() or not str(row["indicator"]).strip():
        raise ValueError("Prediction must include a release date and indicator")
    sample_type = row.get("sample_type", "live")
    if sample_type not in SAMPLE_TYPES:
        raise ValueError(f"sample_type must be one of {SAMPLE_TYPES}")
    probabilities = {name: float(row[f"p_{name}"]) for name in ("above", "inline", "below")}
    if any(not math.isfinite(value) or value < 0 or value > 1 for value in probabilities.values()):
        raise ValueError("Probabilities must be finite values between 0 and 1")
    if abs(sum(probabilities.values()) - 1.0) > 0.005:
        raise ValueError("Probabilities must sum to 1 (within 0.005 for CSV rounding)")
    outcome = str(row["outcome"]).strip()
    if outcome and outcome not in ("above", "inline", "below"):
        raise ValueError(f"Unknown outcome: {outcome!r}")
    return {**row, "sample_type": sample_type}


def append_prediction(row, path=LOG_PATH):
    """Append once per release and indicator, preserving all prediction values."""
    path = Path(path)
    record = _validate_row({"sample_type": "live", **row})
    frame = load_predictions(path)
    key = (str(record["release"]), str(record["indicator"]))
    existing_keys = set(zip(frame["release"].astype(str), frame["indicator"].astype(str)))
    if key in existing_keys:
        raise ValueError(f"A prediction already exists for {key[1]} on {key[0]}")
    updated = pd.concat([frame, pd.DataFrame([record], columns=LOG_COLUMNS)], ignore_index=True)
    temp_path = path.with_name(path.name + ".tmp")
    updated.to_csv(temp_path, index=False)
    os.replace(temp_path, path)
