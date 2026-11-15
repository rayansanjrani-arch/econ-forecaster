# Econ Forecaster

Econ Forecaster is a small research project for estimating probabilities around scheduled US economic releases and checking those probabilities against simple baselines. The longer-term plan is to study whether economic events and volatility help explain gold moves. It is an educational research project, not financial advice.

## Current status

The repository currently has FRED pulls for core CPI and initial claims, a daily gold futures downloader, CPI and claims probability scripts, a prediction log, Brier scoring, and a 104-week walk-forward claims backtest. The log contains one backfilled CPI result and one live claims result; those two observations are not enough to establish predictive value. The claims backtest reports Brier 0.654, compared with 0.667 for uniform guessing and 0.642 for a full-window constant-frequency reference. The latter uses outcomes from the complete test window and is only a diagnostic, not a deployable baseline.

ALFRED first-release vintages, a release calendar, broad consensus history, and a gold event study are not implemented yet. Historical FRED data can be revised, so current-vintage backtests should not be treated as final evidence.

## Setup

Use Python 3.10 or newer.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run commands from the repository directory:

```powershell
python src/fetch_cpi.py
python src/fetch_gold.py
python src/validate_gold.py
python src/error_stats.py
python src/cpi_errors.py
python src/claims_stats.py
python src/backtest_claims.py
python src/backtest_v2.py
python src/score.py
```

`src/predict_claims.py` downloads current FRED claims observations, estimates odds around a 4-week average (or a consensus value passed as its first argument), and appends a live prediction to `logs/predictions.csv`. Check the printed release date against the official calendar, especially around holidays, before relying on it.

```powershell
python src/predict_claims.py
python src/predict_claims.py 194750
```

`src/predict_cpi.py` takes core consensus, headline consensus, and the release date. It prints a dry run by default; add `save` to append the live prediction.

```powershell
python src/predict_cpi.py 0.2 0.3 2026-12-10
python src/predict_cpi.py 0.2 0.3 2026-12-10 save
```

`src/fetch_gold.py` downloads daily OHLCV for Yahoo Finance ticker `GC=F` from 2019 onward using `yfinance` and writes `data/raw/gold_gc_futures_daily.csv`. Earlier Yahoo rows had inconsistent OHLC ordering, and the 2012–2018 sample had weekday gaps that did not match the holiday calendar, so the chosen sample starts in 2019. The validator checks weekday gaps against U.S. federal holidays and Good Friday and stops if it finds an unexplained gap. It also reports close-to-close moves over 5% (which may be market moves or contract-roll effects) for review; it does not automatically fill or adjust them. The file includes the ticker, source, and UTC download timestamp. Raw data files are ignored by Git. This is a COMEX gold futures series, not a spot-price series. Yahoo’s `XAUUSD=X` spot proxy was unavailable when checked, and the retired FRED/LBMA daily gold fix could not serve as a current source.

Score completed rows and inspect calibration:

```powershell
python src/score.py
```

Run the unit tests:

```powershell
python -m unittest discover -s tests
```

## Prediction and scoring rules

- A claims result is **above** when actual claims exceed the forecast by more than 3,000, **below** when actual claims are more than 3,000 under it, and **inline** at either band edge or between them.
- A CPI result uses core CPI as the primary comparison after rounding to one decimal place. Headline CPI breaks a tie when core equals consensus; both equal means inline.
- Every stored prediction includes above/inline/below probabilities that sum to 1. A release and indicator pair can only be logged once.
- The scoreboard separates live from backfilled results, shows indicator-level Brier scores, compares uniform guessing and a prequential historical-frequency baseline, and reports calibration bins. Backfilled results are not evidence of live performance.
- Record forecasts before the result. Do not change their probabilities or outcomes afterward. Corrections to metadata should be documented.

## Project roadmap

The staged project plan is maintained in the accompanying “Econ Forecaster Layers, Tasks and Subtasks” document. Near-term work is to improve data provenance and outcome recording, expand first-release and consensus datasets, and keep documenting experiments including negative results. Do not add a model to the main system unless it improves on a baseline in time-ordered evaluation across multiple windows.

## Repository layout

```text
src/                  Research scripts and shared helpers
data/raw/             Downloaded source files; ignored by Git
data/processed/       Curated datasets such as cpi_history.csv
logs/                 Prediction records
reports/              Generated summaries and figures
tests/                Unit tests
```

`src/config.py` holds project paths, FRED series identifiers, forecast windows, probability thresholds, and simulation settings. Data and log paths are resolved from the repository location, so the scripts work when launched from its root.
