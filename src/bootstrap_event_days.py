"""Task 2.3.4: bootstrap uncertainty intervals for release vs ordinary gold moves."""

import argparse

from config import (BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, EVENT_CONTROL_MATCHES_FILE,
                    EVENT_UNCERTAINTY_FILE, GOLD_SESSION_OUTCOMES_FILE)
from event_uncertainty import bootstrap_comparison, save_uncertainty


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", default=EVENT_CONTROL_MATCHES_FILE)
    parser.add_argument("--sessions", default=GOLD_SESSION_OUTCOMES_FILE)
    parser.add_argument("--output", default=EVENT_UNCERTAINTY_FILE)
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    parser.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    args = parser.parse_args()
    try:
        result = bootstrap_comparison(args.matches, args.sessions, args.resamples, args.seed)
        path = save_uncertainty(result, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Wrote {len(result)} rows to {path} ({args.resamples} resamples, seed {args.seed})")
    primary = result[result["primary_test"]]
    print("\nPrimary test: median scaled move, release / ordinary, with 95% event-bootstrap interval")
    print(primary[["sample", "group", "ratio", "ratio_ci_low", "ratio_ci_high",
                   "share_resamples_ratio_above_1", "n_events", "verdict"]].round(3).to_string(index=False))
    print("\nVerdict rule (declared before results): ratio >= 1.25 and interval lower end > 1.0 = survives; "
          "lower end >= 1.25 = strong. Descriptive daily associations, not causal effects.")


if __name__ == "__main__":
    main()
