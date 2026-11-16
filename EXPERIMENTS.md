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

## 2026-11-16: Reproducibility and pandas-compatibility fixes
- Observation: rebuilding `event_reactions.csv` on a different OS produced last-digit floating-point differences (e.g. `...6325` vs `...6103`) with no real data change, creating noisy diffs.
- Change: saved reaction prices and percentages are rounded to 8 decimals; blank cells for events without gold sessions stay blank. Values and counts are unchanged (327 rows, 252 usable, 323 single-event eligible).
- Change: appending the first row to an empty prediction log or outcome ledger no longer calls `pd.concat` with an empty frame, which raised a pandas FutureWarning about future dtype behaviour.
- Validation: 44 unit tests pass with FutureWarnings treated as errors; a new test checks rounding and blank preservation.

## 2026-11-16: Task 2.3.1 plan — daily gold outcome measures (declared before results)
- Question: define the move measures used to compare release days with ordinary days, calculated identically for every gold session.
- Input: `data/raw/gold_gc_futures_daily.csv` (Yahoo `GC=F` futures, 2019 onward). Output: `data/processed/gold_session_outcomes.csv`, one row per session.
- Measures: signed close-to-close return % from the prior observed session; absolute return %; high-low range as % of prior close (same definition as Task 2.2); trailing volatility = sample standard deviation (ddof=1) of the previous 20 session returns, excluding the current session; scaled move = absolute return / trailing volatility.
- Rules: all 20 prior returns must exist, otherwise trailing volatility and scaled move stay blank and the row is flagged `insufficient_history`. Returns span holiday gaps as observed sessions, as in Task 2.2. Moves above 5% are flagged for review and kept, not removed.
- Fixed now, tested later as separate one-factor checks: the 20-session window (60-session sensitivity deferred).
- Acceptance checks: hand-checkable fixture values; changing a session's own close does not change its trailing volatility (no look-ahead); for usable release events, returns and ranges match `event_reactions.csv`; full test suite passes.

## 2026-11-16: Task 2.3.1 result — daily gold outcome measures built
- Output: `data/processed/gold_session_outcomes.csv`, 1,982 sessions (2019-01-02 to 2026-11-13); 1,961 have a 20-session trailing volatility (first: 2019-02-01). Built by `python src/build_session_outcomes.py`.
- Acceptance checks passed: hand-checked fixture; no look-ahead in trailing volatility; all 252 usable Task 2.2 events match this table exactly (return and range differences 0, same prior session); 52 unit tests pass.
- Inspection: median absolute daily move 0.57%, median range 1.35%, median trailing volatility 0.95%. Six moves above 5% remain flagged (largest -10.78% on 2026-01-30). Three January 2019 events lack trailing volatility because history starts 2019-01-02.
- Data-quality finding: Yahoo `GC=F` volume is very low from January 2019 to May 2020 (224 of 252 sessions in 2019 and 86 in early 2020 under 1,000 contracts; median volume from June 2020 is roughly 190,000). That period also has 30 flat high=low bars. These bars probably do not track the active contract, so their ranges and possibly closes are unreliable. 51 of the 252 usable events fall on thin-volume sessions.
- Decision: added review flags `thin_volume_flag` (volume under 1,000) and `flat_bar_flag`; no rows removed or adjusted. Whether the Task 2.3 comparison sample starts on 2020-06-01 must be declared in the Task 2.3.2 plan before any comparison is calculated.

## 2026-11-16: Task 2.3.2 plan — matched ordinary comparison days (declared before results)
- Question: for each usable release event, which ordinary gold sessions serve as its comparison days? This subtask builds and checks the matches only; no event-versus-ordinary move comparison is calculated here (that is Task 2.3.3).
- Inputs: `data/processed/event_reactions.csv` and `data/processed/gold_session_outcomes.csv`. Output: `data/processed/event_control_matches.csv`, one row per event/comparison-day pair.
- Samples: main sample uses sessions on or after 2020-06-01 because of the thin-volume finding in Task 2.3.1; the full sample (all sessions with a 20-session trailing volatility, from 2019-02-01) is built only as a secondary check. Both events and comparison days must be inside the sample, and both must have trailing volatility.
- Events: single-event eligible rows with an observed gold event session. Overlapping events are not matched, but their sessions still count as release days.
- Release days: every gold session aligned to any event in the event table (all event types, including overlapping events). Comparison days cannot be a release day or within 1 session before or after one.
- Matching rule: same weekday as the event session, within 30 observed sessions before or after it; take up to 5 nearest by session distance, ties broken by the earlier date. No randomness. A comparison day may serve more than one event; later uncertainty work will resample by event.
- Known limitation: before November 2026 the calendar has only BLS CPI, PPI and Employment Situation history. Historical FOMC, GDP, retail-sales and weekly claims days are not marked, so some comparison days are other release days; Thursday comparison days coincide with weekly claims. This makes event/ordinary differences conservative and is documented rather than fixed in this subtask.
- Acceptance checks: fixture tests for weekday matching, release-day and adjacent-day exclusion, nearest-5 order and tie rule, sample-start boundary, events with fewer than 5 matches, overlap handling, and identical output on rerun. Inspect counts per sample and event type, events with fewer than 5 matches, and confirm no comparison day is a release day.

## 2026-11-16: Task 2.3.2 result — matched ordinary comparison days built
- Output: `data/processed/event_control_matches.csv`, 2,246 event/comparison-day pairs. Built by `python src/build_event_controls.py`. No event-versus-ordinary move comparison has been calculated yet.
- Main sample (from 2020-06-01): 201 events (67 CPI, 67 Employment Situation, 67 PPI) and 1,002 comparison-day pairs. 199 events have the full 5; the first two events in the sample have fewer (2020-06-05 Employment Situation: 3, 2020-06-11 PPI: 4) because the sample start cuts their earlier candidates.
- Full sample (secondary check): 249 events and 1,244 pairs. The three January 2019 events are not matched because they lack trailing volatility; 2019-02-01 Employment Situation has 4 comparison days.
- Checks passed: no comparison day is a release day or adjacent to one; all weekdays match; maximum distance is 29 sessions; no main-sample comparison day precedes 2020-06-01; comparison days are balanced before and after events (502 vs 500). 58 unit tests pass.
- Note for Task 2.3.4: comparison days are shared between nearby events (628 unique days for 1,002 main-sample pairs; up to 5 events share one day). Uncertainty must resample by event or account for this sharing, not treat the 1,002 pairs as independent.
- Note: the only four overlap-flagged events are scheduled for 2027, so the overlap rule removes no historical events at present.

## 2026-11-16: Task 2.3.3 plan — release days versus matched ordinary days (declared before results)
- Question: are gold moves on CPI, PPI and Employment Situation release days larger than on their matched ordinary days? Descriptive only; uncertainty intervals are Task 2.3.4.
- Inputs: `data/processed/event_control_matches.csv` and `data/processed/gold_session_outcomes.csv`. Both groups take their values from the same session table. Output: `reports/event_vs_ordinary_summary.csv`.
- Samples: main sample from 2020-06-01 is the primary result; the full sample is a secondary check reported alongside it.
- Groups: each event type separately and all three pooled.
- Release-day values: one per matched event. Ordinary-day values: one per event/ordinary-day pair, so a day shared by several events counts once per pair and each event's own comparison set is preserved.
- Size measures: absolute return %, high-low range %, scaled move (absolute return / trailing 20-session volatility). Statistics: median, 75th and 90th percentile (pandas linear interpolation), release minus ordinary difference, and release / ordinary ratio.
- Direction: median signed return and share of sessions with a positive return.
- Counts reported with every row: events, pairs, unique ordinary days.
- Practical margin, declared now for the later Layer 2 decision gate: a group is "practically larger" only if its median scaled move is at least 1.25 times the ordinary-day median, and that must later survive the Task 2.3.4 uncertainty intervals and window checks. Statistical significance alone will not count.

## 2026-11-16: Task 2.3.3 result — release days versus matched ordinary days (descriptive)
- Output: `reports/event_vs_ordinary_summary.csv` (88 rows). Built by `python src/compare_event_days.py`. No uncertainty intervals yet; Task 2.3.4 adds them.
- Main sample (from 2020-06-01), median scaled move, release vs ordinary (ratio): Employment Situation 0.861 vs 0.546 (1.58, 67 events); PPI 0.678 vs 0.563 (1.20, 67); CPI 0.547 vs 0.565 (0.97, 67); all three pooled 0.658 vs 0.557 (1.18, 201 events, 1,002 pairs).
- Employment Situation is the only group above the declared 1.25 practical margin in the main sample, and it is larger on absolute return (median 0.84% vs 0.56%) and range (1.63% vs 1.28%) as well. CPI shows no larger typical move; its range is about 14% wider.
- Full sample (secondary check, includes the unreliable early-2019/2020 bars): Employment Situation falls to 1.16, so the result is sensitive to the sample period. All full-sample groups sit between 1.11 and 1.16.
- Direction: no group shows a clear tendency for gold to rise or fall on release days (share of up days 0.51-0.57 for releases vs 0.55-0.57 for ordinary days).
- Caution: Employment Situation comparison days are heavily shared (194 unique days for 333 pairs) because the releases fall on nearby Fridays; only 67 events per group. Ordinary days include unmarked FOMC, GDP, retail and claims days. Decision: no conclusion yet; Task 2.3.4 must show whether the Employment Situation difference survives event-resampled uncertainty intervals before it can count toward the Layer 2 gate.
- Design change during this subtask: ratios are left blank for signed-return rows because a ratio of near-zero signed medians is not meaningful. 64 unit tests pass.

## 2026-11-16: Task 1.1a plan — independent gold cross-check source (declared before download)
- Why: `GC=F` has only internal checks. A spot-check of the largest move (2026-01-30, close $4,745.10) matched published reports of the April contract closing near $4,745, but the reported percentage drop (11.4%) differs from ours (10.8%) because Yahoo's prior close is not the official settlement. Contract rolls and the thin-volume 2019 to May 2020 period are unverified.
- Source: SPDR Gold Shares ETF `GLD` from Yahoo via the existing yfinance downloader, saved separately to `data/raw/gold_gld_etf_daily.csv`. Reasons: large and liquid, holds physical gold, no futures rolls, pays no dividends. Limit: NYSE hours (9:30 a.m.-4:00 p.m. ET), so its close is at a different time from the futures close and its high-low range does not include the 8:30 a.m. release moment; close-to-close returns do include it. It is a fund price (including a small expense drag), not spot.
- Validation: the same checks as `GC=F`. Allowed extra NYSE closure: 2025-01-09 (national day of mourning for President Carter). Any other unexplained gap stops the download for review rather than being added silently.
- Step 2 comparison (output `reports/gold_source_check.csv`): returns are calculated on dates present in both sources only, so both returns cover the same period. Report by year: correlation of daily and 5-session returns, median absolute difference, and days where daily returns differ by more than 1.5 percentage points (flagged for review, not removed). Dates present in only one source are listed.
- Step 3 (separate subtask): rebuild the Task 2.3 outputs from GLD with unchanged rules and compare with the `GC=F` results. GLD is a sensitivity check; switching the primary source would be a separate, logged decision.

## 2026-11-16: Task 1.1a result (step 2) — GC=F agrees with the GLD cross-check
- GLD download: 1,980 rows from 2019-01-02; all 74 missing weekdays are holidays or the declared 2025-01-09 NYSE closure; no OHLC errors.
- Agreement on 1,979 common dates: daily return correlation 0.911, 5-session correlation 0.975, median daily difference 0.21 percentage points. By year, daily correlation is 0.85 (2019) to 0.94; 5-session correlation is 0.96-0.99 in every year. The thin-volume period before 2020-06-01 agrees about as well on closes (0.889 daily, 0.975 5-session) as the main sample (0.915, 0.976), so the early problem is mainly in OHLC ranges and flat bars, not closes.
- 34 days differ by more than 1.5 points. Many come in consecutive opposite-sign pairs (e.g. 2019-08-01/02, 2020-06-10/11, 2023-12-13/14, 2024-12-18/19, 2026-06-11/12, 2026-06-17/18): the same move lands on different dates because the futures and ETF closes are at different times. Several are Federal Reserve decision days (2:00 p.m. ET), e.g. 2020-06-10, 2021-06-16, 2022-03-16, 2023-12-13 and 2024-12-18, consistent with Yahoo's GC=F daily close falling before the decision. Interpretation: a 2:00 p.m. event can appear on the next GC=F bar but the same-day GLD bar. This does not affect 8:30 a.m. BLS releases but must be handled before FOMC events are analysed.
- GC=F's 2020-03-23/24 moves above 5% have no matching GLD move, consistent with the March 2020 futures-versus-spot dislocation; GLD's large moves are 2020-08-11, 2025-10-21, 2026-01-30 and 2026-02-03, all also large in GC=F.
- Dates only in GC=F: 2023-11-23, 2025-01-09, 2025-07-04 (exchange-holiday sessions); only in GLD: 2026-11-16.
- Bug found: the download ran at 11:13 a.m. ET, so the 2026-11-16 GLD bar was an incomplete trading session. Fix: `fetch_gold.py` now skips bars dated on or after the current New York date (tested). The GLD file must be re-downloaded.
- Decision: GC=F closes are confirmed as broadly reliable for 8:30 a.m. releases from 2019; no change of primary source. Next is step 3, rebuilding Task 2.3 from GLD as a sensitivity check.

## 2026-11-16: Task 1.1a step 3 plan — Task 2.3 rebuilt from GLD (declared before results)
- GLD re-downloaded after the incomplete-bar fix: 1,979 rows, 2019-01-02 to 2026-11-13, all gaps explained.
- Method: rerun the unchanged Task 2.2, 2.3.1, 2.3.2 and 2.3.3 commands with `--gold`/`--sessions` pointed at GLD; write outputs to `reports/sensitivity_gld/` so the primary GC=F outputs are untouched. Same samples, matching rule, measures and 1.25 practical margin.
- What counts as agreement: the same groups land on the same side of the 1.25 median scaled-move margin. Primary comparison measure is the scaled close-to-close move; GLD's high-low range excludes the 8:30 a.m. pre-open period, so range differences are expected and are not used to judge agreement.

## 2026-11-16: Task 1.1a step 3 result — Task 2.3 findings hold on GLD
- Outputs in `reports/sensitivity_gld/` (event reactions, session outcomes, matches, summary); same counts as GC=F (252 usable events; main sample 201 events and 1,002 pairs).
- Median scaled-move ratio, main sample, GC=F vs GLD: Employment Situation 1.575 vs 1.558; PPI 1.203 vs 1.062; CPI 0.967 vs 0.958; pooled 1.180 vs 1.100. Every group lands on the same side of the 1.25 margin in both sources, so the declared agreement test passes.
- Full sample: Employment Situation is 1.164 on GC=F but 1.472 on GLD. The drop seen earlier when 2019 to May 2020 was added appears to come from the unreliable early GC=F bars rather than from the jobs-report effect itself.
- PPI and CPI are weaker on GLD (median absolute move ratio below 1 for both in the main sample), so neither shows a release-day effect in the typical move.
- Decision: keep GC=F as the primary source; report GLD as the standing sensitivity check in Task 2.3.4 and later. GLD is a credible candidate for extending history before 2019, which remains a separate decision requiring verified pre-2019 BLS release dates.
