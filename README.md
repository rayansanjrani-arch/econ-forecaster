# Econ Forecaster

Econ Forecaster is a small research project for estimating probabilities around scheduled US economic releases and checking those probabilities against simple baselines. The longer-term plan is to study whether economic events and volatility help explain gold moves. It is an educational research project, not financial advice.

## Current status

The repository currently has FRED pulls for core CPI and initial claims, a CPI and a claims probability script, a prediction log, Brier scoring, and a 104-week walk-forward claims backtest. The log contains one backfilled CPI result and one live claims result; those two observations are not enough to establish predictive value. The claims backtest reports Brier 0.654, compared with 0.667 for uniform guessing and 0.642 for a full-window constant-frequency reference. The latter uses outcomes from the complete test window and is only a diagnostic, not a deployable baseline.

Gold data, ALFRED first-release vintages, a release calendar, broad consensus history, and a gold event study are not implemented yet. Historical FRED data can be revised, so current-vintage backtests should not be treated as final evidence.

## Setup

Use Python 3.10 or newer.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run commands from the repository directory:

```powershell
python fetch_cpi.py
python error_stats.py
python claims_stats.py
python backtest_claims.py
python backtest_v2.py
python score.py
```

`predict_claims.py` downloads current FRED claims observations, estimates odds around a 4-week average (or a consensus value passed as its first argument), and appends a live prediction. Check the printed release date against the official calendar, especially around holidays, before relying on it.

```powershell
python predict_claims.py
python predict_claims.py 194750
```

`predict_cpi.py` takes core consensus, headline consensus, and the release date. It prints a dry run by default; add `save` to append the live prediction.

```powershell
python predict_cpi.py 0.2 0.3 2026-12-10
python predict_cpi.py 0.2 0.3 2026-12-10 save
```

Score completed rows and inspect calibration:

```powershell
python score.py
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
