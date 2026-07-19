# VERIFIERS — candidate gate lab

Counterfactual analysis of candidate BUY filters ('verifiers') against the live
track record. **Nothing is blocked in production** — this measures what each gate
*would have* done. Regenerate with:

```bash
scanner/.venv/bin/python scanner/verifier_lab.py --study --write
```

_Last refreshed from bar **2026-07-17** — 40 seasoned entries (≥2d held), 10 negative-excess._

## Live exchange rates

| Gate | Blocked bad | Blocked good | Blocked avg excess | Passed avg excess |
|---|---|---|---|---|
| Entry >2.5% above SMA200 (chased) | 7 | 9 | 1.13pp | 2.71pp |
| Fib resistance <2% overhead | 4 | 3 | 0.3pp | 2.45pp |
| Extended AND resistance overhead | 3 | 0 | -2.13pp | 2.42pp |
| Sector lagging at entry | 4 | 8 | 1.83pp | 2.18pp |
| Earnings growth negative | 4 | 8 | 1.77pp | 2.21pp |
| Re-fire within 14d (whipsaw) | 2 | 8 | 1.71pp | 2.2pp |

A gate earns promotion only if, over months, it blocks clearly negative excess
while the passed set stays positive — AND it survives two-window backtest
validation (see SWEEP.md for why single-window results flip).

## Historical event study — extension gate (150 US tickers, ~2y, forward 20 trading days vs SPY)

| Cohort | Crosses | Avg excess | Median excess | Beat SPY |
|---|---|---|---|---|
| Extended (> 2.5% above SMA200) | 120 | -0.47pp | -0.9pp | 45% |
| Normal (≤ 2.5%) | 590 | -0.65pp | -1.31pp | 43% |

_One window only — preliminary. Promotion requires the full two-window bar._

## Caveats

- Live sample is tiny and young; patterns have already flipped week-to-week.
- Returns are split- but not dividend-adjusted; entries assume alert-day close.
- Gate definitions live in `scanner/verifier_lab.py` (thresholds at top).
