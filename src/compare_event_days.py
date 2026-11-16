"""Task 2.3.3: summarise gold moves on release days versus matched ordinary days."""

import argparse

from config import EVENT_COMPARISON_FILE, EVENT_CONTROL_MATCHES_FILE, GOLD_SESSION_OUTCOMES_FILE
from event_comparison import compare_release_and_ordinary_days, save_comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", default=EVENT_CONTROL_MATCHES_FILE)
    parser.add_argument("--sessions", default=GOLD_SESSION_OUTCOMES_FILE)
    parser.add_argument("--output", default=EVENT_COMPARISON_FILE)
    args = parser.parse_args()
    try:
        summary = compare_release_and_ordinary_days(args.matches, args.sessions)
        path = save_comparison(summary, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Wrote {len(summary)} summary rows to {path}")
    for sample in summary["sample"].unique():
        view = summary[summary["sample"] == sample]
        print(f"\n{sample} sample — release day vs matched ordinary days (descriptive, no uncertainty yet)")
        table = view.pivot_table(index=["group", "measure", "statistic"],
                                 values=["release_value", "ordinary_value", "ratio"], sort=False)
        print(table[["release_value", "ordinary_value", "ratio"]].round(3).to_string())
        counts = view.drop_duplicates("group").set_index("group")[["n_events", "n_pairs", "n_unique_ordinary_days"]]
        print(counts.to_string())


if __name__ == "__main__":
    main()
