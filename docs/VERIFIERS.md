# VERIFIERS — candidate gate lab

Counterfactual analysis of candidate BUY filters ('verifiers') against the live
track record. **Nothing is blocked in production** — this measures what each gate
*would have* done. Regenerate with:

```bash
scanner/.venv/bin/python scanner/verifier_lab.py --study --write
```

_Last refreshed from bar **2026-07-31** — 127 seasoned entries (≥2d held), 60 negative-excess._

## Live exchange rates

| Gate | Blocked bad | Blocked good | Blocked avg excess | Passed avg excess |
|---|---|---|---|---|
| Entry >2.5% above SMA200 (chased) | 23 | 27 | 0.04pp | 1.25pp |
| Fib resistance <2% overhead | 10 | 9 | -1.33pp | 1.15pp |
| Extended AND resistance overhead | 3 | 4 | -0.86pp | 0.87pp |
| Sector lagging at entry | 15 | 13 | 0.14pp | 0.96pp |
| Earnings growth negative | 7 | 19 | 2.35pp | 0.37pp |
| Weak balance sheet (lev/liquidity, ex fin/REIT/util) | 15 | 4 | -2.36pp | 1.33pp |
| Re-fire within 14d (whipsaw) | 19 | 23 | 2.09pp | 0.13pp |

A gate earns promotion only if, over months, it blocks clearly negative excess
while the passed set stays positive — AND it survives two-window backtest
validation (see SWEEP.md for why single-window results flip).

## Two-window multi-model study — cross filters (150 US tickers, forward 20 trading days vs SPY)

Does filtering SMA200 bull crosses by each model beat taking every cross?
With 12 models under test, one lucky pass is expected — promotion needs BOTH
windows agreeing with a clear margin.

| Window | Model | Kept n | Kept avg | Kept beat | Dropped n | Dropped avg | Baseline avg |
|---|---|---|---|---|---|---|---|
| recent | Volume confirms (>=1.25x 20d avg) | 359 | 0.22pp | 47% | 822 | -0.73pp | -0.44pp |
| recent | SMA200 rising (trend quality) | 684 | -0.18pp | 45% | 497 | -0.8pp | -0.44pp |
| recent | RSI < 70 at entry | 1109 | -0.42pp | 46% | 72 | -0.78pp | -0.44pp |
| recent | Fib support 0-3% below (quality-score band) | 521 | -0.67pp | 46% | 660 | -0.26pp | -0.44pp |
| recent | No Fib resistance <2% overhead (live gate) | 1042 | -0.44pp | 45% | 139 | -0.42pp | -0.44pp |
| recent | Close above KAMA(21) at entry | 805 | -0.63pp | 44% | 376 | -0.03pp | -0.44pp |
| recent | KAMA(21) rising (adaptive trend) | 549 | -0.24pp | 46% | 632 | -0.62pp | -0.44pp |
| recent | Above KAMA AND KAMA rising | 488 | -0.32pp | 46% | 693 | -0.52pp | -0.44pp |
| recent | Held 2 closes above (enter day-2 close) | 744 | -0.28pp | 46% | 428 | -2.67pp | -0.44pp |
| recent | Market regime (SPY > its SMA200) | 1032 | -0.46pp | 46% | 149 | -0.3pp | -0.44pp |
| recent | Rising SMA200 AND SPY regime up | 568 | -0.19pp | 46% | 613 | -0.67pp | -0.44pp |
| recent | Volume confirms AND SMA200 rising | 197 | 1.18pp | 51% | 984 | -0.76pp | -0.44pp |
| earlier | Volume confirms (>=1.25x 20d avg) | 978 | -0.27pp | 48% | 2434 | 0.33pp | 0.16pp |
| earlier | SMA200 rising (trend quality) | 1943 | 0.31pp | 51% | 1469 | -0.04pp | 0.16pp |
| earlier | RSI < 70 at entry | 3230 | 0.23pp | 51% | 182 | -1.08pp | 0.16pp |
| earlier | Fib support 0-3% below (quality-score band) | 1601 | 0.01pp | 51% | 1811 | 0.29pp | 0.16pp |
| earlier | No Fib resistance <2% overhead (live gate) | 3028 | 0.09pp | 50% | 384 | 0.68pp | 0.16pp |
| earlier | Close above KAMA(21) at entry | 2194 | 0.11pp | 51% | 1218 | 0.25pp | 0.16pp |
| earlier | KAMA(21) rising (adaptive trend) | 1451 | 0.2pp | 50% | 1961 | 0.13pp | 0.16pp |
| earlier | Above KAMA AND KAMA rising | 1255 | 0.11pp | 50% | 2157 | 0.19pp | 0.16pp |
| earlier | Held 2 closes above (enter day-2 close) | 2082 | 0.14pp | 52% | 1330 | -1.32pp | 0.16pp |
| earlier | Market regime (SPY > its SMA200) | 2797 | 0.14pp | 50% | 615 | 0.22pp | 0.16pp |
| earlier | Rising SMA200 AND SPY regime up | 1606 | 0.3pp | 51% | 1806 | 0.03pp | 0.16pp |
| earlier | Volume confirms AND SMA200 rising | 564 | 0.34pp | 50% | 2848 | 0.12pp | 0.16pp |

## Caveats

- Live sample is tiny and young; patterns have already flipped week-to-week.
- Returns are split- but not dividend-adjusted; entries assume alert-day close.
- Gate definitions live in `scanner/verifier_lab.py` (thresholds at top).
