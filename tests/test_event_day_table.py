import sys, tempfile, unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from event_day_table import EVENT_DAY_COLUMNS, NEWS_EVENT_COLUMNS, build_event_day_table
from outcome_log import OUTCOME_COLUMNS
from release_calendar import CALENDAR_COLUMNS

CHECKED = "2026-11-15T14:00:00+00:00"

def add_calendar(path, rows):
    pd.DataFrame(rows, columns=CALENDAR_COLUMNS).to_csv(path, index=False)

def row(day, indicator, event="Release", period="Reference period"):
    return [day, indicator, event, period, "08:30 AM ET", "https://agency.example/schedule", CHECKED]

def add_news(path, rows):
    pd.DataFrame(rows, columns=NEWS_EVENT_COLUMNS).to_csv(path, index=False)

class EventDayTableTests(unittest.TestCase):
    def test_builds_source_linked_schedule_row(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cal = root / "calendar.csv"
            add_calendar(cal, [row("2026-12-10", "core_cpi_mom", "CPI", "November 2026")])
            table = build_event_day_table(cal, root / "no-outcomes.csv", root / "no-news.csv")
            item = table.iloc[0]
            self.assertEqual(table.columns.tolist(), EVENT_DAY_COLUMNS)
            self.assertEqual(item["event_id"], "scheduled:2026-12-10:core_cpi_mom")
            self.assertEqual(item["event_type"], "core_cpi_mom")
            self.assertEqual(item["public_timestamp_utc"], "2026-12-10T13:30:00+00:00")
            self.assertEqual(item["source_record_id"], "release_calendar:2026-12-10:core_cpi_mom")
            self.assertEqual(item["event_date_et"], "2026-12-10")
            self.assertEqual(item["overlap_policy"], "eligible_for_single_event_analysis")

    def test_joins_cpi_consensus_and_keeps_claims_model_forecast_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cal, outcomes = root / "calendar.csv", root / "outcomes.csv"
            add_calendar(cal, [
                row("2026-12-10", "core_cpi_mom", "CPI"),
                row("2026-12-10", "initial_claims", "Claims"),
            ])
            pd.DataFrame([
                ["2026-12-10", "core_cpi_mom", .3, .2, .2, .3, 0, "above", "BLS", "https://agency.example/cpi", CHECKED],
                ["2026-12-10", "initial_claims", 200000, "", 194750, "", 3000, "above", "DOL", "https://agency.example/claims", CHECKED],
            ], columns=OUTCOME_COLUMNS).to_csv(outcomes, index=False)
            table = build_event_day_table(cal, outcomes, root / "no-news.csv")
            cpi = table.loc[table.indicator == "core_cpi_mom"].iloc[0]
            claims = table.loc[table.indicator == "initial_claims"].iloc[0]
            self.assertEqual(cpi["first_release_value"], .3)
            self.assertEqual(cpi["consensus_value"], .2)
            self.assertAlmostEqual(cpi["consensus_surprise"], .1)
            self.assertEqual(cpi["outcome_source_url"], "https://agency.example/cpi")
            self.assertEqual(claims["saved_forecast_value"], 194750)
            self.assertEqual(claims["consensus_value"], "")
            self.assertEqual(claims["consensus_surprise"], "")

    def test_flags_same_day_news_and_release_as_overlap_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cal, news = root / "calendar.csv", root / "news.csv"
            add_calendar(cal, [row("2026-12-10", "core_cpi_mom", "CPI")])
            add_news(news, [[
                "news-001", "2026-12-10T14:10:00Z", "Trade statement",
                "Headline about tariffs", "", "government_political_statement", 3,
                "story-1", "Official source", "https://agency.example/post", "Timestamp verified",
            ]])
            table = build_event_day_table(cal, root / "no-outcomes.csv", news)
            self.assertEqual(len(table), 2)
            self.assertTrue(table.overlap_flag.all())
            self.assertEqual(table.same_day_event_count.tolist(), [2, 2])
            self.assertEqual(table.events_within_60m.tolist(), [1, 1])
            self.assertEqual(table.overlap_group_id.nunique(), 1)
            self.assertTrue(table.overlap_policy.eq("exclude_from_single_event_analysis").all())

    def test_validates_news_timezone_taxonomy_severity_duplicates_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cal, news = root / "calendar.csv", root / "news.csv"
            add_calendar(cal, [])
            item = ["news-001", "2026-12-10 09:10", "Headline", "Headline", "",
                    "sanctions", 3, "story-1", "Publisher", "https://example.org/a", "Evidence"]
            add_news(news, [item])
            with self.assertRaisesRegex(ValueError, "timezone offset"):
                build_event_day_table(cal, root / "missing.csv", news)
            item[1] = "2026-12-10T14:10:00Z"
            item[5] = "misc"
            add_news(news, [item])
            with self.assertRaisesRegex(ValueError, "Unsupported news event category"):
                build_event_day_table(cal, root / "missing.csv", news)
            item[5], item[6] = "sanctions", 6
            add_news(news, [item])
            with self.assertRaisesRegex(ValueError, "severity"):
                build_event_day_table(cal, root / "missing.csv", news)
            item[6], item[9] = 3, "not-a-url"
            add_news(news, [item])
            with self.assertRaisesRegex(ValueError, "absolute HTTP"):
                build_event_day_table(cal, root / "missing.csv", news)
            item[9] = "https://example.org/a"
            add_news(news, [item, item])
            with self.assertRaisesRegex(ValueError, "duplicate event_id"):
                build_event_day_table(cal, root / "missing.csv", news)

if __name__ == "__main__":
    unittest.main()
