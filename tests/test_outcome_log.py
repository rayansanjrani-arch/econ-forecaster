import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outcome_log import (
    completed_predictions,
    load_outcomes,
    record_claims_outcome,
    record_cpi_outcome,
)
from prediction_log import append_prediction


class OutcomeLogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.predictions = root / "predictions.csv"
        self.outcomes = root / "first_release_outcomes.csv"

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_prediction(self, release, indicator, note="test forecast"):
        append_prediction({
            "release": release,
            "indicator": indicator,
            "made_on": "2026-12-01",
            "p_above": 0.4,
            "p_inline": 0.2,
            "p_below": 0.4,
            "outcome": "",
            "note": note,
        }, path=self.predictions)

    def test_claims_first_release_is_recorded_once_and_used_by_scorer(self):
        self.add_prediction("2026-12-10", "initial_claims")
        record_claims_outcome(
            "2026-12-10", 204000, 200000, "DOL", "https://example.test/release",
            prediction_path=self.predictions, outcome_path=self.outcomes,
            recorded_at_utc="2026-12-10T14:00:00+00:00",
        )
        self.assertEqual(load_outcomes(self.outcomes).loc[0, "outcome"], "above")
        self.assertEqual(completed_predictions(self.predictions, self.outcomes).loc[0, "outcome"], "above")
        with self.assertRaisesRegex(ValueError, "already exists"):
            record_claims_outcome(
                "2026-12-10", 203000, 200000, "DOL", "https://example.test/revised",
                prediction_path=self.predictions, outcome_path=self.outcomes,
            )
        self.assertEqual(len(load_outcomes(self.outcomes)), 1)

    def test_claims_rejects_outcome_without_matching_prediction(self):
        with self.assertRaisesRegex(ValueError, "No forecast exists"):
            record_claims_outcome(
                "2026-12-10", 204000, 200000, "DOL", "https://example.test/release",
                prediction_path=self.predictions, outcome_path=self.outcomes,
            )

    def test_cpi_uses_rounded_core_then_headline_tiebreaker(self):
        self.add_prediction("2026-12-10", "core_cpi_mom")
        row = record_cpi_outcome(
            "2026-12-10", 0.24, 0.35, 0.2, 0.3, "BLS", "https://example.test/cpi",
            prediction_path=self.predictions, outcome_path=self.outcomes,
        )
        self.assertEqual(row["outcome"], "above")
        self.assertEqual(row["actual"], 0.24)
        self.assertEqual(row["actual_secondary"], 0.35)

    def test_legacy_prediction_with_saved_outcome_is_not_changed(self):
        append_prediction({
            "release": "2026-12-10", "indicator": "initial_claims", "made_on": "2026-12-01",
            "p_above": 0.4, "p_inline": 0.2, "p_below": 0.4, "outcome": "below",
            "note": "existing result",
        }, path=self.predictions)
        with self.assertRaisesRegex(ValueError, "already has an outcome"):
            record_claims_outcome(
                "2026-12-10", 204000, 200000, "DOL", "https://example.test/release",
                prediction_path=self.predictions, outcome_path=self.outcomes,
            )
        self.assertEqual(pd.read_csv(self.predictions).loc[0, "outcome"], "below")


if __name__ == "__main__":
    unittest.main()
