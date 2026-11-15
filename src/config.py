"""Project paths and tunable parameters for the current research scripts."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"

CPI_HISTORY_FILE = PROCESSED_DATA_DIR / "cpi_history.csv"
PREDICTIONS_FILE = LOGS_DIR / "predictions.csv"

FRED_GRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
CLAIMS_SERIES = "ICSA"
CORE_CPI_SERIES = "CPILFESL"
HEADLINE_CPI_SERIES = "CPIAUCSL"

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
