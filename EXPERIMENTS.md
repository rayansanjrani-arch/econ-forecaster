# Experiments log

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