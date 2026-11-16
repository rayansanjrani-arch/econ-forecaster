"""Save official BLS yearly release-schedule pages as raw source files.

The pages are stored unchanged under data/raw/bls/schedules/ with a manifest
(URL, retrieval time, size, SHA-256) so every parsed release date can be traced
back to the exact page it came from. Parsing is a separate step.
"""

import argparse
import csv
import hashlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from config import BLS_SCHEDULE_RAW_DIR, BLS_SCHEDULE_URL, BLS_SCHEDULE_YEARS

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
MANIFEST_COLUMNS = ["year", "url", "file", "retrieved_at_utc", "bytes", "sha256", "status"]


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int, default=list(BLS_SCHEDULE_YEARS))
    args = parser.parse_args()
    BLS_SCHEDULE_RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = BLS_SCHEDULE_RAW_DIR / "manifest.csv"
    new_file = not manifest.exists()
    failures = 0
    with manifest.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        if new_file:
            writer.writeheader()
        for year in args.years:
            url = BLS_SCHEDULE_URL.format(year=year)
            retrieved = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            row = {"year": year, "url": url, "retrieved_at_utc": retrieved, "file": "", "bytes": 0, "sha256": ""}
            try:
                body = fetch(url)
                path = BLS_SCHEDULE_RAW_DIR / f"{year}.htm"
                path.write_bytes(body)
                row.update(file=path.name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), status="ok")
                print(f"{year}: saved {len(body):,} bytes")
            except (urllib.error.URLError, TimeoutError) as exc:
                failures += 1
                row["status"] = f"error: {exc}"
                print(f"{year}: FAILED ({exc})")
            writer.writerow(row)
            time.sleep(1.5)  # be polite to bls.gov
    print(f"\nManifest: {manifest}")
    if failures:
        raise SystemExit(f"{failures} year(s) failed; paste this output so the source can be checked.")


if __name__ == "__main__":
    main()
