import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alfred_data import (
    ALFRED_MANIFEST_COLUMNS,
    build_alfred_request,
    fetch_and_archive_vintage,
    fetch_vintage_frame,
    parse_vintage_date,
)


API_KEY = "a" * 32


def api_response(series_id, observations, vintage_date="2026-11-14"):
    return {
        "realtime_start": vintage_date,
        "realtime_end": vintage_date,
        "observations": [
            {"realtime_start": vintage_date, "realtime_end": vintage_date,
             "date": day, "value": value}
            for day, value in observations
        ],
    }


class AlfredDataTests(unittest.TestCase):
    def test_rejects_invalid_and_future_vintage_dates(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            parse_vintage_date("2026-2-03")
        tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "future"):
            parse_vintage_date(tomorrow)

    def test_request_uses_https_and_single_vintage_with_api_key_parameter(self):
        request = build_alfred_request("CPILFESL", "2026-11-14", API_KEY)
        parsed_url = urlsplit(request.full_url)
        query = parse_qs(parsed_url.query)
        self.assertEqual(parsed_url.scheme, "https")
        self.assertEqual(parsed_url.hostname, "api.stlouisfed.org")
        self.assertEqual(query["vintage_dates"], ["2026-11-14"])
        self.assertEqual(query["output_type"], ["1"])
        self.assertEqual(query["api_key"], [API_KEY])

    def test_fetch_normalizes_observations_and_preserves_missing_values(self):
        payload = api_response("CPILFESL", [
            ("2026-09-01", "338.9"), ("2026-10-01", ".")
        ])

        def requester(_request, timeout):
            self.assertEqual(timeout, 30)
            return io.BytesIO(json.dumps(payload).encode("utf-8"))

        frame, metadata = fetch_vintage_frame(
            "CPILFESL", "2026-11-14", api_key=API_KEY, requester=requester
        )
        self.assertEqual(frame.columns.tolist(), ["observation_date", "CPILFESL"])
        self.assertEqual(frame["observation_date"].tolist(), ["2026-09-01", "2026-10-01"])
        self.assertEqual(frame.loc[1, "CPILFESL"], ".")
        self.assertEqual(metadata["api_realtime_start"], "2026-11-14")

    def test_fetch_rejects_empty_or_error_api_responses(self):
        def empty_requester(_request, **_kwargs):
            return io.BytesIO(json.dumps({"observations": []}).encode("utf-8"))

        with self.assertRaisesRegex(ValueError, "no observations"):
            fetch_vintage_frame("CPILFESL", "2026-11-14", API_KEY, empty_requester)

        def error_requester(_request, **_kwargs):
            return io.BytesIO(json.dumps({"error_code": 400, "error_message": "bad request"}).encode("utf-8"))

        with self.assertRaisesRegex(RuntimeError, "API error 400"):
            fetch_vintage_frame("CPILFESL", "2026-11-14", API_KEY, error_requester)

    def test_archives_validated_batch_and_manifest(self):
        observations = {
            "CPILFESL": [("2026-09-01", "338.9"), ("2026-10-01", "339.1")],
            "ICSA": [("2026-10-31", "191000"), ("2026-11-07", "200000")],
        }

        def requester(request, **_kwargs):
            series_id = parse_qs(urlsplit(request.full_url).query)["series_id"][0]
            return io.BytesIO(json.dumps(api_response(series_id, observations[series_id])).encode("utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_id, snapshot_dir, manifest_path, rows = fetch_and_archive_vintage(
                "2026-11-14", ["CPILFESL", "ICSA"], api_key=API_KEY,
                requester=requester, snapshot_dir=root / "snapshots",
                manifest_path=root / "alfred" / "manifest.csv",
                fetched_at_utc="2026-11-15T14:02:54+00:00",
            )
            self.assertEqual(snapshot_id, "asof_20261114_20261115T140254Z")
            self.assertTrue((snapshot_dir / "CPILFESL.csv").exists())
            self.assertTrue((snapshot_dir / "ICSA.csv").exists())
            manifest = pd.read_csv(manifest_path, keep_default_na=False)
            self.assertEqual(manifest.columns.tolist(), ALFRED_MANIFEST_COLUMNS)
            self.assertEqual(manifest["series_id"].tolist(), ["CPILFESL", "ICSA"])
            self.assertTrue((root / manifest.loc[0, "snapshot_file"]).exists())
            self.assertEqual(len(rows), 2)

    def test_invalid_series_prevents_partial_archive(self):
        def requester(request, **_kwargs):
            series_id = parse_qs(urlsplit(request.full_url).query)["series_id"][0]
            if series_id == "CPILFESL":
                observations = [("2026-09-01", "338.9"), ("2026-10-01", "339.1")]
            else:
                observations = [("2026-10-30", "200000"), ("2026-11-06", "201000")]
            return io.BytesIO(json.dumps(api_response(series_id, observations)).encode("utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "Saturday-weekly"):
                fetch_and_archive_vintage(
                    "2026-11-14", ["CPILFESL", "ICSA"], api_key=API_KEY,
                    requester=requester, snapshot_dir=root / "snapshots",
                    manifest_path=root / "manifest.csv",
                    fetched_at_utc="2026-11-15T14:02:54+00:00",
                )
            self.assertFalse((root / "snapshots" / "2026-11-14").exists())
            self.assertFalse((root / "manifest.csv").exists())

    def test_missing_api_key_fails_with_setup_instruction(self):
        with self.assertRaisesRegex(ValueError, "FRED_API_KEY is not set"):
            build_alfred_request("CPILFESL", "2026-11-14", "")


if __name__ == "__main__":
    unittest.main()
