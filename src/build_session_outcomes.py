"""Build Task 2.3.1 daily gold move measures for every session."""

import argparse

from config import GOLD_HISTORY_FILE, GOLD_SESSION_OUTCOMES_FILE, GOLD_TRAILING_VOL_WINDOW
from session_outcomes import calculate_session_outcomes, save_session_outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=GOLD_HISTORY_FILE)
    parser.add_argument("--output", default=GOLD_SESSION_OUTCOMES_FILE)
    parser.add_argument("--window", type=int, default=GOLD_TRAILING_VOL_WINDOW)
    args = parser.parse_args()
    try:
        outcomes = calculate_session_outcomes(args.gold, args.window)
        path = save_session_outcomes(outcomes, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    usable = int((~outcomes["insufficient_history"]).sum())
    print(f"Wrote {len(outcomes)} gold sessions to {path}")
    print(f"Sessions with a {args.window}-session trailing volatility: {usable}; insufficient history: {len(outcomes) - usable}")
    print(f"Sessions flagged as moves above 5% (kept for review): {int(outcomes['large_move_flag'].sum())}")
    thin = int(outcomes["thin_volume_flag"].eq(True).sum())
    flat = int(outcomes["flat_bar_flag"].sum())
    print(f"Review flags (kept, not removed): thin volume {thin}, flat high=low bars {flat}")


if __name__ == "__main__":
    main()
