"""Record a first-reported claims or CPI outcome with source provenance."""

import argparse

from outcome_log import record_claims_outcome, record_cpi_outcome
from config import FIRST_RELEASE_OUTCOMES_FILE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="kind", required=True)

    claims = subparsers.add_parser("claims", help="record initial claims")
    claims.add_argument("release", help="release date (YYYY-MM-DD)")
    claims.add_argument("actual", type=float, help="first-reported initial claims")
    claims.add_argument("--forecast", required=True, type=float, help="forecast saved before release")
    claims.add_argument("--source", required=True, help="source name, e.g. U.S. DOL release")
    claims.add_argument("--source-url", required=True, help="URL to the first release")

    cpi = subparsers.add_parser("cpi", help="record core CPI and headline tie-breaker")
    cpi.add_argument("release", help="release date (YYYY-MM-DD)")
    cpi.add_argument("core_actual", type=float)
    cpi.add_argument("headline_actual", type=float)
    cpi.add_argument("--core-consensus", required=True, type=float)
    cpi.add_argument("--headline-consensus", required=True, type=float)
    cpi.add_argument("--source", required=True, help="source name, e.g. U.S. BLS CPI release")
    cpi.add_argument("--source-url", required=True, help="URL to the first release")

    args = parser.parse_args()
    if args.kind == "claims":
        record_claims_outcome(
            args.release, args.actual, args.forecast, args.source, args.source_url,
        )
    else:
        record_cpi_outcome(
            args.release, args.core_actual, args.headline_actual,
            args.core_consensus, args.headline_consensus, args.source, args.source_url,
        )
    print(f"First-release outcome saved to {FIRST_RELEASE_OUTCOMES_FILE}")


if __name__ == "__main__":
    main()
