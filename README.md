# Econ Forecaster

Econ Forecaster is a small research project for estimating probabilities around scheduled US economic releases and checking those probabilities against simple baselines. The longer-term plan is to study whether economic events and volatility help explain gold moves. It is an educational research project, not financial advice.

## Current status

The repository currently has FRED prediction pulls for core CPI and initial claims, a batch FRED data refresh for eight economic series, a daily gold futures downloader, CPI and claims probability scripts, a prediction log, a first-release outcome log, a manually verified release calendar, Brier scoring, and a 104-week walk-forward claims backtest. The prediction log contains one backfilled CPI result and one live claims result; those two observations are not enough to establish predictive value. The claims backtest reports Brier 0.654, compared with 0.667 for uniform guessing and 0.642 for a full-window constant-frequency reference. The latter uses outcomes from the complete test window and is only a diagnostic, not a deployable baseline.

ALFRED point-in-time snapshot retrieval is implemented, but it is not yet connected to forecast generation or backtests. Layer 2 builds a source-linked gold event-day table and descriptive daily reaction metrics. The release calendar now includes historical CPI, PPI, and Employment Situation release events covering 2019–2025, alongside the upcoming multi-agency schedule. Historical coverage remains incomplete and this sample is only an early pipeline check, not enough for broad conclusions. The 2025 shutdown caused several releases to be delayed or canceled; the event ledger uses actual publication dates and documents the omitted releases. A rolling weekly claims schedule and broad consensus history are also future work. Historical FRED data can be revised, so current-vintage backtests should not be treated as final evidence.

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
python src/fetch_economic_data.py
python src/fetch_gold.py
python src/validate_gold.py
python src/release_calendar.py
python src/error_stats.py
python src/cpi_errors.py
python src/claims_stats.py
python src/backtest_claims.py
python src/backtest_v2.py
python src/score.py
```

`python src/fetch_economic_data.py` refreshes the configured FRED series as one validated batch: core CPI, headline CPI, final-demand PPI, nonfarm payrolls, unemployment, initial claims, real GDP, and advance retail sales. It validates dates, duplicates, numeric values, and the expected monthly, Saturday-weekly, or quarterly spacing before writing any files. Each successful refresh creates an immutable snapshot under `data/raw/fred/snapshots/` and appends source, units, frequency, retrieval time, row counts, missing-value counts and dates, and date coverage to `data/raw/fred/manifest.csv`. Use `--series ICSA --series PAYEMS` to fetch selected series. FRED's `.` missing-value markers are retained in the snapshots and listed in the manifest. These are current-vintage FRED observations and can change when agencies revise history; they are not ALFRED first-release vintages. Raw files are ignored by Git.

ALFRED point-in-time snapshots are fetched separately with `src/fetch_alfred_vintage.py`. The official FRED API requires a personal API key. Request one from [your FRED account](https://fredaccount.stlouisfed.org/), then enter it into the current PowerShell session without putting it in project files or command history:

```powershell
$secureKey = Read-Host "FRED API key" -AsSecureString
$env:FRED_API_KEY = [Net.NetworkCredential]::new("", $secureKey).Password
Remove-Variable secureKey
python src/fetch_alfred_vintage.py --vintage-date 2026-11-14
```

The command fetches all configured series for one requested ALFRED as-of date; repeat `--series` to fetch selected series. It validates the complete batch before writing an immutable snapshot under `data/raw/fred/alfred/snapshots/` and adds source, retrieval date, observation coverage, and missing-value details to `data/raw/fred/alfred/manifest.csv`. Each request uses the FRED API's `vintage_dates` parameter. The Version 1 API requires `api_key` in its HTTPS query; the program reads it from the environment and does not print or save it. The date is day-granular, not an intraday release timestamp: for a forecast made before a release on a given day, use the prior calendar date as the information cutoff. These snapshots are point-in-time input data, not a full backtest; forecast generation and scoring against first-reported outcomes remain separate work.

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

`data/processed/release_calendar.csv` holds manually verified release dates and source links for CPI, PPI, Employment Situation (payrolls, unemployment and earnings), FOMC decisions, BEA GDP estimates, and Census advance retail sales. `python src/release_calendar.py` lists the next 90 days, with UTC and Pakistan time conversions plus same-day/within-60-minute overlap flags. Use `--days 180` for a longer window or `--all` for the complete file. Eastern daylight-saving changes are applied by date. The 2027 FOMC entries are tentative per the Federal Reserve's revised schedule; the October strategy meeting is not listed as a rate decision. DOL publishes the weekly claims report weekly but does not provide a forward holiday-adjusted calendar, so add each claims date only after its official announcement rather than guessing holiday shifts.



### Layer 2: event-day table

Run **python src/build_event_day_table.py** to build **data/processed/event_day_table.csv** from the release calendar, first-release outcome log, and manually curated **data/processed/news_events.csv**. Scheduled rows link back to a release-calendar record and, when available, an outcome source. CPI consensus surprises are calculated only from the CPI outcome recorder's explicit consensus fields. Other saved forecasts, including claims forecasts, are kept distinct from consensus.

Add unscheduled headlines only after verifying the first-public timestamp and source. Each news row needs a unique event ID, timezone-aware timestamp, category, severity from 1 to 5, publisher, source URL, and evidence note; story_id links repeated updates. Allowed categories are geopolitical_escalation, sanctions, tariffs_trade, government_political_statement, central_bank_surprise, corporate_technology_shock, and energy_supply_disruption. Do not guess timestamps or add illustrative events as data.

The table retains every event but flags records on the same Eastern date or within 60 minutes in a stable overlap group. The predefined policy is to exclude flagged events from single-event reaction estimates; keep the records for later grouped analysis. Unique events remain eligible. The calendar currently contains BLS CPI, PPI, and Employment Situation events for 2019–2025 reference periods plus future scheduled entries. Some 2025 data releases occurred in January 2026 after shutdown delays. Additional historical records should be added only from verified source records.

### Layer 2: daily gold reaction metrics

Run `python src/analyze_event_reactions.py` to join the event table to the downloaded `GC=F` daily gold bars and write `data/processed/event_reactions.csv`. Event-session returns are close-to-close from the prior available gold session to the first available gold bar dated on or after the Eastern event date. One-, three-, and five-session returns use that same prior close as the reference; the daily high-low range is also scaled by the prior close. Horizon counts are observed gold sessions, not calendar days. Upcoming events are retained with an explicit no-session status, and overlapping events remain in the output but are marked ineligible for single-event estimates. Daily bars only support descriptive day-level associations; they do not identify intraday reactions or causal effects. The 2019–2025 historical sample validates the calculation pipeline; broader event comparisons require extending verified historical coverage and applying the planned comparison and uncertainty analysis.

### Layer 2: Task 2.3 event days versus ordinary days

Run `python src/build_session_outcomes.py` to write `data/processed/gold_session_outcomes.csv`: one row per gold session with signed and absolute close-to-close returns, high-low range scaled by the prior close, trailing 20-session volatility (excluding the current session), and the absolute move divided by that volatility. Review flags mark moves above 5%, thin volume (under 1,000 contracts) and flat high=low bars; no rows are removed. Yahoo `GC=F` volume is very low from January 2019 to May 2020, so Task 2.3 uses a main sample starting 2020-06-01 and treats the full sample as a secondary check.

Then run `python src/build_event_controls.py` to write `data/processed/event_control_matches.csv`. Each usable, non-overlapping release event is matched to up to five ordinary sessions on the same weekday within 30 sessions, excluding release days and the sessions next to them; the nearest sessions are chosen, earlier date first on ties. The calendar does not yet mark historical FOMC, GDP, retail-sales or weekly claims days, so some comparison days are other release days. The matching rules are recorded in `EXPERIMENTS.md`.

### Layer 2: Task 2.3.4 uncertainty and 2005-2018 replication

`python src/bootstrap_event_days.py` adds 95% event-bootstrap intervals (2,000 resamples, fixed seed) to the release-versus-ordinary comparison and applies the pre-declared rule: median scaled-move ratio at least 1.25 with an interval lower end above 1.0. Output: `reports/event_vs_ordinary_uncertainty.csv`.

The replication uses data not examined when the pattern was found. `python src/fetch_gold.py --long-history` downloads GLD from November 2004 to a separate file. `python src/build_replication_calendar.py` parses the verbatim BLS schedule extracts in `data/raw/bls/schedule_extracts/` into `data/processed/release_calendar_2005_2018.csv`. `python src/run_replication.py` then repeats Tasks 2.2-2.3.4 with unchanged rules for 2005-2018 and its 2005-2011 and 2012-2018 halves, writing to `reports/replication_2005_2018/`. Results and decisions are recorded in `EXPERIMENTS.md`.

After a forecast has been logged and the agency publishes its first release, record the reported value and source. Outcomes are stored separately in append-only `data/processed/first_release_outcomes.csv`; `score.py` joins them to predictions without editing forecast records. Duplicate outcomes and outcomes without a matching forecast are rejected.

```powershell
python src/record_outcome.py claims 2026-12-10 204000 --forecast 201000 --source "U.S. DOL weekly claims release" --source-url "https://www.dol.gov/newsroom/releases"
python src/record_outcome.py cpi 2026-12-10 0.2 0.3 --core-consensus 0.2 --headline-consensus 0.3 --source "U.S. BLS CPI release" --source-url "https://www.bls.gov/news.release/cpi.htm"
```

The claims command expects the first-reported claims value and the forecast saved before release. The CPI command expects the published core and headline month-over-month values plus both consensus values used for the forecast. Use the direct agency release URL when recording a real outcome, not the generic example URLs above. The tool records a UTC timestamp and the comparison values used to classify the result.

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
