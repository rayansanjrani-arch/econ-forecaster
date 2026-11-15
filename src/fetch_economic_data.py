"""Refresh and archive the configured current-vintage FRED economic series."""

import argparse

from config import FRED_SERIES_CATALOG
from economic_data import fetch_and_archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--series", action="append", choices=sorted(FRED_SERIES_CATALOG),
        help="fetch one series (repeat the option); default fetches all configured series",
    )
    args = parser.parse_args()
    snapshot_id, snapshot_dir, manifest_path, rows = fetch_and_archive(args.series)
    print(f"Snapshot {snapshot_id}: {snapshot_dir}")
    for row in rows:
        missing_dates = row["missing_observation_dates"] or "none"
        print(
            f"{row['series_id']}: {row['rows']:,} rows, "
            f"{row['first_observation']} to {row['last_observation']}, "
            f"{row['missing_values']} missing ({missing_dates}); "
            f"{row['frequency']}; {row['units']}"
        )
    print(f"Manifest: {manifest_path}")
    print("These are current-vintage FRED observations, not first-release ALFRED vintages.")


if __name__ == "__main__":
    main()
