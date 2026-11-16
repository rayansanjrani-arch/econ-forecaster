# Experiments log

## 2026-11-15: Standardized current-vintage FRED snapshots
- Added a shared fetch/validation command for core and headline CPI, final-demand PPI, total nonfarm payrolls, unemployment rate, initial claims, real GDP, and advance retail sales.
- Checked series definitions and units against official FRED metadata: CPILFESL/CPIAUCSL, PPIFIS, PAYEMS, UNRATE, ICSA, GDPC1 and RSAFS. Frequencies are monthly except weekly Saturday-ending claims and quarterly real GDP.
- Each successful batch writes immutable per-series CSVs in a timestamped raw snapshot directory and appends a manifest with source, units, frequency, retrieval time, row counts, missing values and observation coverage.
- Validated live batch (snapshot `20261115T144013Z`) fetched all eight series. Three series have a blank FRED value at `2025-10-01` (core CPI, headline CPI and unemployment); the snapshot retains the blank rows and the manifest identifies them. No rows are silently filled or interpolated.
- Decision: preserve current-vintage downloads for reproducibility but do not use them as first-release labels; ALFRED vintage support remains a separate task. Any failed series or quality check aborts the whole batch before writing a partial snapshot.
- Tests cover frequency spacing, duplicate/invalid dates, invalid numeric values, snapshot/manifest output and atomic rejection of a failed batch.

## 2026-11-15: Expand verified release calendar
- Added agency-scheduled dates for CPI, PPI and Employment Situation releases, plus FOMC policy decision dates. BLS dates were checked against its release-specific schedules; the 2027 FOMC rows use the Federal Reserve's revised November 12 tentative schedule.
- Each event retains its source URL and UTC check timestamp. The calendar command converts Eastern release times to UTC and Pakistan local time using timezone rules, and flags same-day and within-60-minute overlaps.
- Decision: do not prefill weekly claims dates around holidays because DOL publishes the claims report weekly but does not provide the same rolling forward calendar. Add each date when its official announcement is available; do not guess holiday shifts.
- Tests cover Eastern Standard/Daylight Time conversion, same-day/near-time overlap flags, duplicate keys and invalid time strings.

## 2026-11-15: Add scheduled GDP and retail releases
- Added BEA GDP advance, second, and third estimate dates from November 2026 through December 2027, with each estimate type and reference quarter stored separately.
- Added Census advance monthly retail and food services release dates from November 2026 through December 2027. The Census schedule has not yet announced the December 2027 data release date, so it is not included.
- Sources: [BEA 2026 schedule](https://www.bea.gov/news/schedule/), [BEA 2027 schedule](https://www.bea.gov/news/schedule/next-year), and [Census 2026/2027 retail schedule](https://www.census.gov/retail/release_schedule.html), checked 2026-11-15.
- Claims dates remain excluded until the Department of Labor confirms each date; no holiday-adjusted weekly dates are inferred.
- Tests verify the calendar includes all 14 listed GDP and 14 retail events and that their agency source URLs are present.

## 2026-11-15: Release calendar and first-release outcome capture
- Added a manual calendar of scheduled CPI dates from the BLS release schedule, with the agency URL and checked date on each row. The next listed release is November 2026 CPI on December 10, 2026 at 8:30 a.m. Eastern.
- Added a separate append-only outcome file. Outcome records retain first-reported values, the forecast/consensus comparison values, source link, and UTC recording timestamp. Scoring joins these outcomes to matching forecasts without editing the prediction log.
- Decision: maintain the calendar manually and verify dates against official agency schedules; do not infer weekly claims dates during holiday weeks. ALFRED point-in-time snapshot retrieval is tracked separately from forecast/backtest integration.
- Validation: outcome capture requires a matching saved forecast and source URL, rejects duplicate results, and keeps existing prediction rows unchanged.

## 2026-11-15: Daily gold source check
- FRED's older LBMA gold-fixing series is no longer available as a current series; Yahoo Finance's `GC=F` provides daily OHLCV, but represents COMEX futures rather than spot.
- The Yahoo `XAUUSD=X` spot symbol returned no data during the source check.
- A direct request for the FRED `GOLDPMGBD228NLBM` CSV also returned HTTP 404, so it cannot provide a daily comparison series at this time.
- Decision: use `GC=F` provisionally for daily data and label the instrument as futures. Flag weekday gaps and moves above 5% for manual holiday/roll review. Do not interpret the series as spot or silently adjust roll jumps.
- Data-quality check: the Yahoo history beginning in 2000 had 441 rows with inconsistent OHLC ordering, concentrated before 2012. The 2012–2018 sample also had two unexplained weekday gaps (2018-01-29 and 2018-12-05); CME's published schedule confirms COMEX metals traded normally on 2018-12-05. The sample therefore starts in 2019, and future unexplained gaps will fail validation rather than pass silently.
- Downloaded sample: 1,982 daily rows from 2019-01-02 through 2026-11-13. The validator found 71 weekday gaps, all matching the configured U.S. federal holiday/Good Friday calendar, and no unexplained weekday gaps or OHLC errors. Six close-to-close changes exceeded 5%; each remains a review candidate, not an automatic correction. Raw bars are ignored by Git.
- Open limitation: no direct spot/futures comparison was available, so large moves may include market moves or contract-roll effects. Resolve a suitable spot source and inspect roll dates before interpreting gold event-study results.

## 2026-11-11: Claims first-release revision
- Observation: the first-reported claims value of 189,000 was later revised to 191,000.
- Implication: current-vintage FRED pulls can change historical labels and backtest errors.
- Decision: keep this limitation visible; obtain ALFRED vintages before treating revised historical backtests as final evidence.

## 2026-11-12: First live claims result
- Forecast: 194,750 using the trailing 4-week average; probabilities were 0.353 above, 0.293 inline and 0.353 below.
- Result: above. Brier score 0.629 versus 0.667 for uniform guessing.
- Decision: keep collecting live observations. One result is not evidence that the model beats a baseline.

## 2026-11-12: CPI consensus-history setup
- Data: one backfilled October observation is present for core and headline CPI.
- Decision: treat the error summary as descriptive only; collect at least 24 months of dated consensus/actual pairs before using it to estimate forecast performance.

## 2026-11-11: Weekly jobless claims, backtest (104 weeks)
- v1 (4-week average forecast, robust spread): Brier 0.654
- Random guessing: 0.667. Constant-odds baseline: 0.642 (uses hindsight)
- Calibration: "below" happened 45% of the time vs 36% predicted
  (claims drifted down in this window)
- Tried adding a recent-error shift (8, 13 and 26 weeks, half and full):
  none beat v1 (best 0.661, worst 0.695). Adjusting for recent misses
  added noise, so v1 stays the live model.
- Caveat: one 2-year window, so differences of ~0.01 are within noise.
- Next: judge v1 on live predictions it hasn't seen.


## 2026-11-15: Add ALFRED point-in-time snapshot fetcher
- Added an authenticated FRED API client for one exact vintage/as-of date using the official `vintage_dates` parameter and observations-by-real-time-period output. The API key is read from `FRED_API_KEY` and supplied over HTTPS in the Version 1 API's required `api_key` query parameter; it is not printed or written to the repository.
- Added all-series/selected-series CLI retrieval, full-batch validation before writes, immutable timestamped vintage snapshots, and a separate manifest containing the vintage date and data coverage.
- Kept ALFRED snapshots separate from current-vintage FRED snapshots; the existing current-vintage fetcher is unchanged. Date-granular ALFRED snapshots do not encode the intraday order of a forecast and release on the same day.
- Offline tests cover request construction, key handling, date validation, missing observations, API errors, atomic batch rejection, and manifest output. A live API fetch still requires the user's FRED API key.


## 2026-11-15: Build Layer 2 event-day table
- Added a deterministic source-linked event table from the verified scheduled-release calendar, first-release outcome ledger, and a manual unscheduled-news ledger.
- Stored event IDs, UTC public timestamps, Eastern event dates, event type/reference period, actual first-release values, explicit CPI consensus values/surprises, and source-record links. Claims forecasts are preserved separately and are not labelled as consensus.
- Added a news source-record schema with timezone-aware first-public timestamps, categories, severity, publisher/source URL, evidence note, and optional story cluster ID. No example headlines were inserted as research data.
- Predefined overlap handling: retain rows and assign stable group IDs for events on the same Eastern date or within 60 minutes; exclude flagged records from single-event analysis while preserving them for possible grouped analysis.
- Tests cover source linkage, first-release/consensus mapping, overlap flags and policy, invalid news timestamps/categories/severity, duplicate event IDs, and bad URLs.
- Historical coverage: added 252 BLS CPI, PPI, and Employment Situation release events for 2019–2025 reference periods. Rows link to official BLS schedules or the revised-date/release archive source and retain the 08:30 a.m. Eastern time. Some December 2025 reference-period releases occurred in January 2026. During the 2025 appropriations lapse, BLS canceled the October CPI and Employment Situation releases and the October PPI release; October PPI values were included with the November PPI publication. Canceled reports are not represented as observed market-release events. Coverage for 2026 reference periods and other event families remains to be added.

## 2026-11-15: Calculate descriptive daily event reactions
- Added event-to-gold-session alignment and close-to-close return calculations for the event session and one-, three-, and five-session horizons, plus the event-session high-low range scaled by the prior close.
- The event session is the first available daily bar dated on or after the Eastern event date; horizon periods count observed futures sessions. Overlapping records are retained with an explicit single-event ineligibility flag.
- Upcoming events and events without adequate history receive status labels instead of fabricated values. The 2019–2025 historical BLS slice can now be joined to the available gold bars; it is a pipeline validation sample, not sufficient evidence for broad impact claims.
- Interpretation limit: Yahoo `GC=F` daily bars support descriptive daily associations only. They cannot establish immediate intraday reactions or causal effects; contract roll moves also remain a data limitation.
