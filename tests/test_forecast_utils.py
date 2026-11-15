import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forecast_utils import brier_score, classify_band_outcome, classify_cpi_outcome, round_half_up


class ForecastUtilsTests(unittest.TestCase):
    def test_rounds_half_up_at_published_precision(self):
        self.assertEqual(round_half_up(0.25), 0.3)
        self.assertEqual(round_half_up(1.24), 1.2)

    def test_band_edges_are_inline(self):
        self.assertEqual(classify_band_outcome(103, 100, 3), "inline")
        self.assertEqual(classify_band_outcome(97, 100, 3), "inline")
        self.assertEqual(classify_band_outcome(103.01, 100, 3), "above")
        self.assertEqual(classify_band_outcome(96.99, 100, 3), "below")

    def test_cpi_uses_core_then_headline_tiebreak(self):
        self.assertEqual(classify_cpi_outcome(0.3, 0.2, 0.1, 0.2), "above")
        self.assertEqual(classify_cpi_outcome(0.1, 0.2, 0.3, 0.2), "below")
        self.assertEqual(classify_cpi_outcome(0.2, 0.2, 0.3, 0.2), "above")
        self.assertEqual(classify_cpi_outcome(0.2, 0.2, 0.2, 0.2), "inline")

    def test_brier_score_for_one_hot_actual(self):
        score = brier_score({"above": 0.8, "inline": 0.1, "below": 0.1}, "above")
        self.assertAlmostEqual(score, 0.06)

    def test_brier_rejects_invalid_probability_totals(self):
        with self.assertRaises(ValueError):
            brier_score({"above": 0.5, "inline": 0.5, "below": 0.5}, "above")


if __name__ == "__main__":
    unittest.main()
