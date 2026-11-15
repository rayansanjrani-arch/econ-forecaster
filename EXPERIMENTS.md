# Experiments log

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
