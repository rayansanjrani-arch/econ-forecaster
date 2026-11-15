"""Fetch and archive a point-in-time ALFRED vintage for configured series."""

import argparse

from config import FRED_SERIES_CATALOG
from alfred_data import fetch_and_archive_vintage, parse_vintage_date


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vintage-date", required=True, type=parse_vintage_date,
                        help="as-of date in YYYY-MM-DD format")
    parser.add_argument(
        "--series", action="append", choices=sorted(FRED_SERIES_CATALOG),
        help="fetch one series (repeat the option); default fetches all configured series",
    )
    args = parser.parse_args()
    try:
        snapshot_id, snapshot_dir, manifest_path, rows = fetch_and_archive_vintage(
            args.vintage_date, args.series
        )
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    print(f"ALFRED vintage {args.vintage_date}: snapshot {snapshot_id}")
    print(f"Snapshot: {snapshot_dir}")
    for row in rows:
        missing_dates = row["missing_observation_dates"] or "none"
        print(
            f"{row['series_id']}: {row['rows']:,} rows, "
            f"{row['first_observation']} to {row['last_observation']}, "
            f"{row['missing_values']} missing ({missing_dates}); {row['frequency']}; {row['units']}"
        )
    print(f"Manifest: {manifest_path}")
    print("Values are the ALFRED vintage for the requested calendar date; the API is date-granular.")


if __name__ == "__main__":
    main()
