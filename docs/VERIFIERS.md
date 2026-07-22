# VERIFIERS — candidate gate lab

Counterfactual analysis of candidate BUY filters ('verifiers') against the live
track record. **Nothing is blocked in production** — this measures what each gate
*would have* done. Regenerate with:

```bash
scanner/.venv/bin/python scanner/verifier_lab.py --study --write
```

_Last refreshed from bar **2026-07-21** — 57 seasoned entries (≥2d held), 34 negative-excess._

## Live exchange rates

| Gate | Blocked bad | Blocked good | Blocked avg excess | Passed avg excess |
|---|---|---|---|---|
| Entry >2.5% above SMA200 (chased) | 15 | 7 | -1.24pp | 0.32pp |
| Fib resistance <2% overhead | 6 | 2 | -1.83pp | -0.03pp |
| Extended AND resistance overhead | 3 | 0 | -5.5pp | 0.01pp |
| Sector lagging at entry | 5 | 8 | 1.15pp | -0.71pp |
| Earnings growth negative | 6 | 9 | 0.32pp | -0.5pp |
| Weak balance sheet (lev/liquidity, ex fin/REIT/util) | 0 | 0 | Nonepp | -0.28pp |
| Re-fire within 14d (whipsaw) | 10 | 5 | -1.33pp | 0.09pp |

A gate earns promotion only if, over months, it blocks clearly negative excess
while the passed set stays positive — AND it survives two-window backtest
validation (see SWEEP.md for why single-window results flip).

## Caveats

- Live sample is tiny and young; patterns have already flipped week-to-week.
- Returns are split- but not dividend-adjusted; entries assume alert-day close.
- Gate definitions live in `scanner/verifier_lab.py` (thresholds at top).
