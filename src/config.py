"""Project paths and tunable parameters for the current research scripts."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
FRED_RAW_DIR = RAW_DATA_DIR / "fred"
FRED_SNAPSHOT_DIR = FRED_RAW_DIR / "snapshots"
FRED_MANIFEST_FILE = FRED_RAW_DIR / "manifest.csv"
ALFRED_RAW_DIR = FRED_RAW_DIR / "alfred"
ALFRED_SNAPSHOT_DIR = ALFRED_RAW_DIR / "snapshots"
ALFRED_MANIFEST_FILE = ALFRED_RAW_DIR / "manifest.csv"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"

CPI_HISTORY_FILE = PROCESSED_DATA_DIR / "cpi_history.csv"
PREDICTIONS_FILE = LOGS_DIR / "predictions.csv"
GOLD_HISTORY_FILE = RAW_DATA_DIR / "gold_gc_futures_daily.csv"
GOLD_CROSSCHECK_FILE = RAW_DATA_DIR / "gold_gld_etf_daily.csv"
GOLD_SOURCE_CHECK_FILE = REPORTS_DIR / "gold_source_check.csv"
RELEASE_CALENDAR_FILE = PROCESSED_DATA_DIR / "release_calendar.csv"
FIRST_RELEASE_OUTCOMES_FILE = PROCESSED_DATA_DIR / "first_release_outcomes.csv"
NEWS_EVENTS_FILE = PROCESSED_DATA_DIR / "news_events.csv"
EVENT_DAY_TABLE_FILE = PROCESSED_DATA_DIR / "event_day_table.csv"
EVENT_REACTIONS_FILE = PROCESSED_DATA_DIR / "event_reactions.csv"
GOLD_SESSION_OUTCOMES_FILE = PROCESSED_DATA_DIR / "gold_session_outcomes.csv"
EVENT_CONTROL_MATCHES_FILE = PROCESSED_DATA_DIR / "event_control_matches.csv"
EVENT_COMPARISON_FILE = REPORTS_DIR / "event_vs_ordinary_summary.csv"

FRED_GRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
CLAIMS_SERIES = "ICSA"
CORE_CPI_SERIES = "CPILFESL"
HEADLINE_CPI_SERIES = "CPIAUCSL"
PPI_SERIES = "PPIFIS"
PAYROLLS_SERIES = "PAYEMS"
UNEMPLOYMENT_SERIES = "UNRATE"
REAL_GDP_SERIES = "GDPC1"
RETAIL_SALES_SERIES = "RSAFS"

# Metadata is checked against each FRED series page. Current-vintage pulls use
# these units/frequencies but do not represent historical ALFRED information sets.
FRED_SERIES_CATALOG = {
    CORE_CPI_SERIES: {
        "name": "Core CPI index",
        "frequency": "monthly",
        "units": "Index 1982-1984=100",
        "seasonal_adjustment": "Seasonally adjusted",
        "source_agency": "U.S. Bureau of Labor Statistics",
    },
    HEADLINE_CPI_SERIES: {
        "name": "CPI index",
        "frequency": "monthly",
        "units": "Index 1982-1984=100",
        "seasonal_adjustment": "Seasonally adjusted",
        "source_agency": "U.S. Bureau of Labor Statistics",
    },
    PPI_SERIES: {
        "name": "Producer Price Index by Commodity: Final Demand",
        "frequency": "monthly",
        "units": "Index Nov 2009=100",
        "seasonal_adjustment": "Seasonally adjusted",
        "source_agency": "U.S. Bureau of Labor Statistics",
    },
    PAYROLLS_SERIES: {
        "name": "All Employees: Total Nonfarm",
        "frequency": "monthly",
        "units": "Thousands of persons",
        "seasonal_adjustment": "Seasonally adjusted",
        "source_agency": "U.S. Bureau of Labor Statistics",
    },
    UNEMPLOYMENT_SERIES: {
        "name": "Unemployment rate",
        "frequency": "monthly",
        "units": "Percent",
        "seasonal_adjustment": "Seasonally adjusted",
        "source_agency": "U.S. Bureau of Labor Statistics",
    },
    CLAIMS_SERIES: {
        "name": "Initial claims",
        "frequency": "weekly",
        "units": "Number",
        "seasonal_adjustment": "Seasonally adjusted; week ending Saturday",
        "source_agency": "U.S. Employment and Training Administration",
    },
    REAL_GDP_SERIES: {
        "name": "Real gross domestic product",
        "frequency": "quarterly",
        "units": "Billions of chained 2017 dollars",
        "seasonal_adjustment": "Seasonally adjusted annual rate",
        "source_agency": "U.S. Bureau of Economic Analysis",
    },
    RETAIL_SALES_SERIES: {
        "name": "Advance retail sales: retail trade and food services",
        "frequency": "monthly",
        "units": "Millions of dollars",
        "seasonal_adjustment": "Seasonally adjusted",
        "source_agency": "U.S. Census Bureau",
    },
}
GOLD_YAHOO_TICKER = "GC=F"
GOLD_SOURCE_NAME = "Yahoo Finance via yfinance"
# Task 1.1a cross-check: SPDR Gold Shares ETF (NYSE hours, no futures rolls, no dividends)
GOLD_CROSSCHECK_TICKER = "GLD"
# Verified non-federal-holiday NYSE closures; add only with a source.
NYSE_EXTRA_CLOSURES = {
    "2025-01-09": "NYSE closed: national day of mourning for President Jimmy Carter",
}
GOLD_SOURCE_DIFF_FLAG_PCT = 1.5  # daily return difference (percentage points) flagged for review
GOLD_START_DATE = "2019-01-01"
GOLD_SPIKE_THRESHOLD = 0.05
GOLD_TRAILING_VOL_WINDOW = 20  # Task 2.3.1: prior sessions, current excluded
GOLD_THIN_VOLUME_THRESHOLD = 1_000  # contracts/day; review flag, not an exclusion
# Task 2.3.2 matched comparison days (declared in EXPERIMENTS.md before results)
MAIN_SAMPLE_START = "2020-06-01"  # after the thin-volume GC=F period
CONTROL_WINDOW_SESSIONS = 30
CONTROLS_PER_EVENT = 5
CONTROL_EVENT_BUFFER_SESSIONS = 1

CLAIMS_BAND = 3_000
CLAIMS_FORECAST_WINDOW = 4
CLAIMS_SPREAD_WINDOW = 52
CLAIMS_BACKTEST_WEEKS = 104
CLAIMS_RECENT_WINDOW = 26

CPI_GAP_LIMIT_DAYS = 40
CPI_FORECAST_WINDOW = 3
CPI_SPREAD_WINDOW = 36
CPI_STATS_WINDOW = 60
CPI_RECENT_BIAS_WINDOW = 12
CPI_MONTE_CARLO_SAMPLES = 200_000
CPI_RANDOM_SEED = 42


def fred_csv_url(series_id):
    """Build a FRED graph CSV URL for a series identifier."""
    return f"{FRED_GRAPH_URL}?id={series_id}"
