# VERIFIERS — candidate gate lab

Counterfactual analysis of candidate BUY filters ('verifiers') against the live
track record. **Nothing is blocked in production** — this measures what each gate
*would have* done. Regenerate with:

```bash
scanner/.venv/bin/python scanner/verifier_lab.py --study --write
```

_Last refreshed from bar **2026-07-23** — 68 seasoned entries (≥2d held), 32 negative-excess._

## Live exchange rates

| Gate | Blocked bad | Blocked good | Blocked avg excess | Passed avg excess |
|---|---|---|---|---|
| Entry >2.5% above SMA200 (chased) | 13 | 12 | -0.38pp | 1.31pp |
| Fib resistance <2% overhead | 6 | 4 | -1.7pp | 1.11pp |
| Extended AND resistance overhead | 2 | 1 | -5.29pp | 0.97pp |
| Sector lagging at entry | 7 | 11 | 0.66pp | 0.71pp |
| Earnings growth negative | 9 | 8 | 0.3pp | 0.82pp |
| Weak balance sheet (lev/liquidity, ex fin/REIT/util) | 0 | 2 | 2.06pp | 0.65pp |
| Re-fire within 14d (whipsaw) | 9 | 12 | -0.27pp | 1.13pp |

A gate earns promotion only if, over months, it blocks clearly negative excess
while the passed set stays positive — AND it survives two-window backtest
validation (see SWEEP.md for why single-window results flip).

## Two-window multi-model study — cross filters (150 US tickers, forward 20 trading days vs SPY)

Does filtering SMA200 bull crosses by each model beat taking every cross?
With 8 models under test, one lucky pass is expected — promotion needs BOTH
windows agreeing with a clear margin.

| Window | Model | Kept n | Kept avg | Kept beat | Dropped n | Dropped avg | Baseline avg |
|---|---|---|---|---|---|---|---|
| recent | Volume confirms (>=1.25x 20d avg) | 358 | 0.25pp | 48% | 825 | -0.78pp | -0.47pp |
| recent | SMA200 rising (trend quality) | 699 | -0.15pp | 45% | 484 | -0.92pp | -0.47pp |
| recent | RSI < 70 at entry | 1109 | -0.44pp | 45% | 74 | -0.84pp | -0.47pp |
| recent | Fib support 0-3% below (quality-score band) | 514 | -0.74pp | 45% | 669 | -0.25pp | -0.47pp |
| recent | No Fib resistance <2% overhead (live gate) | 1042 | -0.5pp | 45% | 141 | -0.2pp | -0.47pp |
| recent | Market regime (SPY > its SMA200) | 1034 | -0.49pp | 46% | 149 | -0.3pp | -0.47pp |
| recent | Rising SMA200 AND SPY regime up | 583 | -0.16pp | 46% | 600 | -0.76pp | -0.47pp |
| recent | Volume confirms AND SMA200 rising | 200 | 1.19pp | 52% | 983 | -0.8pp | -0.47pp |
| earlier | Volume confirms (>=1.25x 20d avg) | 978 | -0.27pp | 48% | 2434 | 0.33pp | 0.16pp |
| earlier | SMA200 rising (trend quality) | 1943 | 0.31pp | 51% | 1469 | -0.04pp | 0.16pp |
| earlier | RSI < 70 at entry | 3230 | 0.23pp | 51% | 182 | -1.08pp | 0.16pp |
| earlier | Fib support 0-3% below (quality-score band) | 1601 | 0.01pp | 51% | 1811 | 0.29pp | 0.16pp |
| earlier | No Fib resistance <2% overhead (live gate) | 3028 | 0.09pp | 50% | 384 | 0.68pp | 0.16pp |
| earlier | Market regime (SPY > its SMA200) | 2797 | 0.14pp | 50% | 615 | 0.22pp | 0.16pp |
| earlier | Rising SMA200 AND SPY regime up | 1606 | 0.3pp | 51% | 1806 | 0.03pp | 0.16pp |
| earlier | Volume confirms AND SMA200 rising | 564 | 0.34pp | 50% | 2848 | 0.12pp | 0.16pp |

## Caveats

- Live sample is tiny and young; patterns have already flipped week-to-week.
- Returns are split- but not dividend-adjusted; entries assume alert-day close.
- Gate definitions live in `scanner/verifier_lab.py` (thresholds at top).
