# Backtest — Phase 1 alerts, last 5 years

*Run 2026-07-05 with `python scanner/backtest.py --report docs/BACKTEST.md`. 26,859 signals, 2021-07 → 2026-07.*

## Findings (read this first)

1. **No rule beat buy-and-hold in this window.** Every rule's mean return sits at or below
   the baseline at 1 year (bull cross −2.5%, death cross −2.8%). The window was a strong
   bull market (+15%/yr baseline); crosses happen after weakness or chop, and this period
   rewarded simply staying invested.
2. **Crossing stocks are choppy stocks.** Price×SMA200 fired ~23k times (~4.4 per ticker
   per year) — names oscillating around their SMA fire repeatedly and underperform trending
   names in *both* directions. A cross means "trend state changed", not "outperformance ahead".
3. **Bear signals contain real relative information.** Stocks kept rising after bear signals
   on average (+11.9% at 1y — shorting them would have lost money), but they lagged the
   baseline by ~3%. Useful as an *underweight/review* trigger, not a short signal.
4. **Death crosses bounce short-term.** +0.8% edge at 1–3 months (the oversold bounce),
   then −2.8% by 1 year. Don't panic-sell on day one of a death cross.
5. **Medians are far below means everywhere** (e.g. bull cross 1y: median +4.9% vs mean
   +12.5%): a few huge winners carry the average; the typical signal is much more modest.

**Practical takeaway:** treat alerts as a watchlist trigger — "this name changed trend
state, look at it" — not as an automatic buy/sell. The dashboard's TradingView links exist
for exactly that review step.

**Caveats:** survivorship bias (today's index members only — delisted losers excluded, so
absolute numbers are optimistic); one 5-year bull-market window; overlapping signals are
not independent; no transaction costs.

---

Universe: 517 tickers (today's S&P 500 + Nasdaq 100 — survivorship bias inflates absolute numbers; compare vs baseline).

**Baseline** = forward return of holding any universe stock from any day in the window.

| Horizon | Baseline mean | Baseline % positive |
|---|---|---|
| 1w | +0.3% | 53% |
| 1m | +1.1% | 54% |
| 3m | +3.1% | 55% |
| 6m | +6.4% | 57% |
| 1y | +15.0% | 60% |

## ▲ PRICE_SMA200_BULL — 11373 signals

| Horizon | n | Mean return | Median | Success rate | Edge vs baseline |
|---|---|---|---|---|---|
| 1w | 11305 | +0.2% | +0.2% | 52% | -0.1% |
| 1m | 11133 | +0.8% | +0.7% | 54% | -0.3% |
| 3m | 10746 | +2.3% | +1.3% | 54% | -0.9% |
| 6m | 10215 | +5.0% | +2.6% | 56% | -1.4% |
| 1y | 9149 | +12.5% | +4.9% | 58% | -2.5% |

## ▼ PRICE_SMA200_BEAR — 11501 signals

| Horizon | n | Mean return | Median | Success rate | Edge vs baseline |
|---|---|---|---|---|---|
| 1w | 11455 | +0.2% | +0.2% | 47% | -0.1% |
| 1m | 11321 | +0.8% | +0.6% | 47% | -0.3% |
| 3m | 10966 | +2.9% | +1.8% | 44% | -0.3% |
| 6m | 10360 | +5.1% | +2.9% | 44% | -1.2% |
| 1y | 9294 | +11.9% | +5.2% | 42% | -3.0% |

## ▲ GOLDEN_CROSS — 1904 signals

| Horizon | n | Mean return | Median | Success rate | Edge vs baseline |
|---|---|---|---|---|---|
| 1w | 1898 | +0.2% | +0.0% | 51% | -0.1% |
| 1m | 1867 | +0.5% | +0.2% | 51% | -0.6% |
| 3m | 1830 | +2.0% | +0.7% | 52% | -1.1% |
| 6m | 1728 | +5.7% | +2.2% | 55% | -0.7% |
| 1y | 1488 | +14.6% | +5.4% | 59% | -0.4% |

## ▼ DEATH_CROSS — 2081 signals

| Horizon | n | Mean return | Median | Success rate | Edge vs baseline |
|---|---|---|---|---|---|
| 1w | 2077 | +0.6% | +0.4% | 45% | +0.3% |
| 1m | 2058 | +1.9% | +1.4% | 42% | +0.8% |
| 3m | 1993 | +3.9% | +2.8% | 42% | +0.8% |
| 6m | 1882 | +5.3% | +2.8% | 44% | -1.0% |
| 1y | 1724 | +12.2% | +5.5% | 41% | -2.8% |

Success rate: share of signals where price moved in the signal's direction 
(up after bullish, down after bearish) by the horizon.
Edge vs baseline: signal's mean return minus the unconditional mean.
