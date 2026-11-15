"""Shared forecast rules used by the live log and its scorer."""

from decimal import Decimal, ROUND_HALF_UP
import math


OUTCOMES = ("above", "inline", "below")


def round_half_up(value, places=1):
    """Round to a fixed number of decimal places using published-value rounding."""
    quantum = Decimal("1").scaleb(-places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def classify_band_outcome(actual, forecast, band):
    """Classify a release; the band edges count as inline."""
    if actual > forecast + band:
        return "above"
    if actual < forecast - band:
        return "below"
    return "inline"


def classify_cpi_outcome(core_actual, core_consensus, headline_actual, headline_consensus):
    """Use core CPI as the primary result and headline CPI as a tie-breaker."""
    if core_actual > core_consensus:
        return "above"
    if core_actual < core_consensus:
        return "below"
    if headline_actual > headline_consensus:
        return "above"
    if headline_actual < headline_consensus:
        return "below"
    return "inline"


def brier_score(probabilities, outcome):
    """Return the multiclass Brier score for an above/inline/below forecast."""
    if outcome not in OUTCOMES:
        raise ValueError(f"Unknown outcome: {outcome!r}")
    values = {name: float(probabilities[name]) for name in OUTCOMES}
    if any(not math.isfinite(value) or value < 0 or value > 1 for value in values.values()):
        raise ValueError("Probabilities must be finite values between 0 and 1")
    if abs(sum(values.values()) - 1.0) > 0.005:
        raise ValueError("Probabilities must sum to 1 (within 0.005 for CSV rounding)")
    return sum((values[name] - (name == outcome)) ** 2 for name in OUTCOMES)
