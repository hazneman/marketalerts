# VERIFIERS — candidate gate lab

Counterfactual analysis of candidate BUY filters ('verifiers') against the live
track record. **Nothing is blocked in production** — this measures what each gate
*would have* done. Regenerate with:

```bash
scanner/.venv/bin/python scanner/verifier_lab.py --study --write
```

_Last refreshed from bar **2026-07-22** — 65 seasoned entries (≥2d held), 36 negative-excess._

## Live exchange rates

| Gate | Blocked bad | Blocked good | Blocked avg excess | Passed avg excess |
|---|---|---|---|---|
| Entry >2.5% above SMA200 (chased) | 12 | 12 | -1.23pp | -0.07pp |
| Fib resistance <2% overhead | 6 | 4 | -2.2pp | -0.18pp |
| Extended AND resistance overhead | 2 | 1 | -5.87pp | -0.23pp |
| Sector lagging at entry | 5 | 11 | 1.1pp | -1.01pp |
| Earnings growth negative | 8 | 8 | -0.27pp | -0.57pp |
| Weak balance sheet (lev/liquidity, ex fin/REIT/util) | 0 | 1 | 2.58pp | -0.54pp |
| Re-fire within 14d (whipsaw) | 13 | 6 | -1.4pp | -0.12pp |

A gate earns promotion only if, over months, it blocks clearly negative excess
while the passed set stays positive — AND it survives two-window backtest
validation (see SWEEP.md for why single-window results flip).

## Two-window event study — re-fire gate (150 US tickers, forward 20 trading days vs SPY)

A cross is a *re-fire* when the same signal fired within the prior 14 calendar days (the live ↩ tag). This IS the two-window bar: both windows must agree before the gate can touch the verdict.

| Window | Cohort | Crosses | Avg excess | Median excess | Beat SPY |
|---|---|---|---|---|---|
| recent | Re-fire | 449 | -0.35pp | -1.2pp | 45% |
| recent | First cross | 730 | -0.53pp | -0.86pp | 45% |
| earlier | Re-fire | 1366 | 0.27pp | 0.26pp | 52% |
| earlier | First cross | 2046 | 0.08pp | -0.03pp | 50% |

## Caveats

- Live sample is tiny and young; patterns have already flipped week-to-week.
- Returns are split- but not dividend-adjusted; entries assume alert-day close.
- Gate definitions live in `scanner/verifier_lab.py` (thresholds at top).
