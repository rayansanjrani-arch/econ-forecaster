# Experiments log

## 2026-11-15: Release calendar and first-release outcome capture
- Added a manual calendar of scheduled CPI dates from the BLS release schedule, with the agency URL and checked date on each row. The next listed release is November 2026 CPI on December 10, 2026 at 8:30 a.m. Eastern.
- Added a separate append-only outcome file. Outcome records retain first-reported values, the forecast/consensus comparison values, source link, and UTC recording timestamp. Scoring joins these outcomes to matching forecasts without editing the prediction log.
- Decision: maintain the calendar manually and verify dates against official agency schedules; do not infer weekly claims dates during holiday weeks. Automated ALFRED imports and correction/version handling remain future work.
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
