import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import FRED_SERIES_CATALOG
from economic_data import MANIFEST_COLUMNS, fetch_and_archive, validate_fred_frame


class EconomicDataTests(unittest.TestCase):
    def test_catalog_series_accept_their_expected_observation_spacing(self):
        dates_by_frequency = {
            "monthly": ["2026-09-01", "2026-10-01"],
            "weekly": ["2026-10-31", "2026-11-07"],
            "quarterly": ["2026-04-01", "2026-07-01"],
        }
        for series_id, metadata in FRED_SERIES_CATALOG.items():
            with self.subTest(series_id=series_id):
                dates = dates_by_frequency[metadata["frequency"]]
                frame = pd.DataFrame({"observation_date": dates, series_id: ["1", "2"]})
                result = validate_fred_frame(frame, series_id)
                self.assertEqual(len(result), 2)
                self.assertEqual(result["observation_date"].tolist(), dates)

    def test_rejects_duplicate_dates_and_wrong_frequency(self):
        duplicate = pd.DataFrame({
            "observation_date": ["2026-10-01", "2026-10-01"],
            "CPILFESL": ["1", "2"],
        })
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_fred_frame(duplicate, "CPILFESL")

        missing_month = pd.DataFrame({
            "observation_date": ["2026-08-01", "2026-10-01"],
            "CPILFESL": ["1", "2"],
        })
        with self.assertRaisesRegex(ValueError, "monthly frequency"):
            validate_fred_frame(missing_month, "CPILFESL")

        wrong_weekday = pd.DataFrame({
            "observation_date": ["2026-10-30", "2026-11-06"],
            "ICSA": ["1", "2"],
        })
        with self.assertRaisesRegex(ValueError, "Saturday-weekly"):
            validate_fred_frame(wrong_weekday, "ICSA")

    def test_rejects_invalid_dates_and_non_numeric_values(self):
        invalid_date = pd.DataFrame({"observation_date": ["not-a-date"], "UNRATE": ["4.2"]})
        with self.assertRaisesRegex(ValueError, "invalid observation date"):
            validate_fred_frame(invalid_date, "UNRATE")

        invalid_value = pd.DataFrame({"observation_date": ["2026-10-01"], "UNRATE": ["bad"]})
        with self.assertRaisesRegex(ValueError, "non-numeric"):
            validate_fred_frame(invalid_value, "UNRATE")

    def test_archives_one_consistent_snapshot_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = {
                "CPILFESL": pd.DataFrame({
                    "observation_date": ["2026-09-01", "2026-10-01"],
                    "CPILFESL": ["338.896", "339.900"],
                }),
                "ICSA": pd.DataFrame({
                    "observation_date": ["2026-10-31", "2026-11-07"],
                    "ICSA": ["191000", "200000"],
                }),
            }

            def reader(url, **_kwargs):
                series_id = url.split("id=")[-1]
                return data[series_id].copy()

            snapshot_id, snapshot_dir, manifest_path, rows = fetch_and_archive(
                ["CPILFESL", "ICSA"],
                reader=reader,
                snapshot_dir=root / "snapshots",
                manifest_path=root / "manifest.csv",
                fetched_at_utc="2026-11-15T14:02:54+00:00",
            )
            self.assertEqual(snapshot_id, "20261115T140254Z")
            self.assertTrue((snapshot_dir / "CPILFESL.csv").exists())
            self.assertTrue((snapshot_dir / "ICSA.csv").exists())
            manifest = pd.read_csv(manifest_path)
            self.assertEqual(manifest["series_id"].tolist(), ["CPILFESL", "ICSA"])
            self.assertEqual(manifest["rows"].tolist(), [2, 2])
            self.assertEqual(len(rows), 2)
            self.assertEqual(manifest.loc[0, "frequency"], FRED_SERIES_CATALOG["CPILFESL"]["frequency"])

    def test_failed_series_does_not_create_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = pd.DataFrame({"observation_date": ["2026-10-01"], "CPILFESL": ["339.9"]})
            bad = pd.DataFrame({"observation_date": ["2026-10-01"], "ICSA": ["200000"]})

            def reader(url, **_kwargs):
                return good.copy() if "CPILFESL" in url else bad.copy()

            with self.assertRaisesRegex(ValueError, "Saturday-weekly"):
                fetch_and_archive(
                    ["CPILFESL", "ICSA"], reader=reader,
                    snapshot_dir=root / "snapshots", manifest_path=root / "manifest.csv",
                    fetched_at_utc="2026-11-15T14:02:54+00:00",
                )
            self.assertFalse((root / "snapshots" / "20261115T140254Z").exists())
            self.assertFalse((root / "manifest.csv").exists())

    def test_manifest_records_missing_value_dates_and_migrates_older_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.csv"
            legacy_columns = [column for column in MANIFEST_COLUMNS if column != "missing_observation_dates"]
            pd.DataFrame([{
                "snapshot_id": "older",
                "series_id": "CPILFESL",
                "series_name": "Core CPI index",
                "frequency": "monthly",
                "units": "index",
                "seasonal_adjustment": "adjusted",
                "source_agency": "BLS",
                "source_url": "https://fred.stlouisfed.org/series/CPILFESL",
                "snapshot_file": "snapshots/older/CPILFESL.csv",
                "fetched_at_utc": "2026-11-14T00:00:00+00:00",
                "rows": 1,
                "missing_values": 0,
                "first_observation": "2026-10-01",
                "last_observation": "2026-10-01",
            }], columns=legacy_columns).to_csv(manifest_path, index=False)

            def reader(_url, **_kwargs):
                return pd.DataFrame({
                    "observation_date": ["2026-09-01", "2026-10-01"],
                    "CPILFESL": ["338.9", "."],
                })

            _, _, _, _ = fetch_and_archive(
                ["CPILFESL"], reader=reader,
                snapshot_dir=root / "snapshots", manifest_path=manifest_path,
                fetched_at_utc="2026-11-15T14:02:54+00:00",
            )
            manifest = pd.read_csv(manifest_path, keep_default_na=False)
            self.assertEqual(manifest.columns.tolist(), MANIFEST_COLUMNS)
            self.assertEqual(manifest.loc[1, "missing_values"], 1)
            self.assertEqual(manifest.loc[1, "missing_observation_dates"], "2026-10-01")
            self.assertEqual(manifest.loc[0, "missing_observation_dates"], "")


if __name__ == "__main__":
    unittest.main()
