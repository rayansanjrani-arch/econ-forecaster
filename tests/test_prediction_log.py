import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prediction_log import append_prediction, load_predictions


class PredictionLogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "predictions.csv"

    def tearDown(self):
        self.temp_dir.cleanup()

    def row(self, release="2026-12-10"):
        return {
            "release": release,
            "indicator": "initial_claims",
            "made_on": "2026-12-03",
            "p_above": 0.4,
            "p_inline": 0.2,
            "p_below": 0.4,
            "outcome": "",
            "note": "4-week average forecast",
        }

    def test_duplicate_release_and_indicator_is_rejected(self):
        append_prediction(self.row(), path=self.path)
        with self.assertRaisesRegex(ValueError, "already exists"):
            append_prediction(self.row(), path=self.path)
        self.assertEqual(len(pd.read_csv(self.path)), 1)

    def test_legacy_backfilled_note_is_classified_without_editing_source(self):
        pd.DataFrame([{
            **self.row(),
            "note": "backfilled from first model - not a true test",
        }]).to_csv(self.path, index=False)
        loaded = load_predictions(self.path)
        self.assertEqual(loaded.loc[0, "sample_type"], "backfilled")
        self.assertNotIn("sample_type", pd.read_csv(self.path).columns)


if __name__ == "__main__":
    unittest.main()
