import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bls_schedule_extracts import build_calendar, coverage_problems, parse_line


class ScheduleParserTests(unittest.TestCase):
    def test_old_format_infers_year_from_reference_month(self):
        row = parse_line("Producer Price Indexes, December 2005 Jan. 13 8:30 am", 2005)
        self.assertEqual((row["release_date"], row["indicator"], row["reference_period"]),
                         ("2006-01-13", "ppi", "December 2005"))
        row = parse_line("Consumer Price Index, December 2004 Jan. 19 8:30 am", 2005)
        self.assertEqual((row["release_date"], row["indicator"]), ("2005-01-19", "core_cpi_mom"))
        row = parse_line("The Employment Situation, March 2005 April 1, 2005 8:30 am", 2005)
        self.assertEqual((row["release_date"], row["indicator"]), ("2005-04-01", "employment_situation"))
        self.assertEqual(parse_line("Consumer Price Indexes, January 2005 Feb. 23 8:30 am", 2005)["indicator"], "core_cpi_mom")
        self.assertEqual(row["source_url"], "https://www.bls.gov/schedule/2005/home.htm")

    def test_new_format_and_weekday_check(self):
        row = parse_line("Tuesday, October 22, 2013 | 08:30 AM | Employment Situation for September 2013", 2013)
        self.assertEqual(row["release_date"], "2013-10-22")
        with self.assertRaisesRegex(ValueError, "Weekday"):
            parse_line("Friday, October 22, 2013 | 08:30 AM | Employment Situation for September 2013", 2013)

    def test_rejects_printed_year_conflict_and_unknown_lines(self):
        with self.assertRaisesRegex(ValueError, "disagrees"):
            parse_line("The Employment Situation, March 2005 April 1, 2006 8:30 am", 2005)
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            parse_line("Real Earnings, March 2005 April 20 8:30 am", 2005)

    def test_cross_page_duplicates_are_merged_and_conflicts_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            (d / "2005.txt").write_text("Producer Price Indexes, December 2005 Jan. 13 8:30 am\n")
            (d / "2006.txt").write_text("Producer Price Indexes, December 2005 Jan. 13 8:30 am\n"
                                        "Producer Price Indexes, January 2006 Feb. 17 8:30 am\n")
            cal = build_calendar(d, "2005-01-01", "2018-12-31")
            self.assertEqual(len(cal), 2)
            self.assertEqual(cal.iloc[0]["source_url"], "https://www.bls.gov/schedule/2006/home.htm")
            self.assertEqual(coverage_problems(cal), [])
            (d / "2006.txt").write_text("Producer Price Indexes, December 2005 Jan. 17 8:30 am\n")
            with self.assertRaisesRegex(ValueError, "disagree"):
                build_calendar(d, "2005-01-01", "2018-12-31")

    def test_coverage_flags_missing_month(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            (d / "2006.txt").write_text("Producer Price Indexes, January 2006 Feb. 17 8:30 am\n"
                                        "Producer Price Indexes, March 2006 April 18 8:30 am\n")
            problems = coverage_problems(build_calendar(d, "2005-01-01", "2018-12-31"))
            self.assertTrue(problems and "2006-02" in problems[0])


if __name__ == "__main__":
    unittest.main()
