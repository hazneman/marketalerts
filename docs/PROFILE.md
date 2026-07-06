# Stock traits vs strategy edge (baseline SMA200/2d model)

500 tickers. Edge = strategy return − buy-and-hold return, last 5 years. Positive edge = the model beat holding that stock.

## 1. Hindsight view — traits measured in the SAME window as the edge

**Volatility (annualized)** — rank correlation with edge: -0.01

| Quintile | Trait range | Mean edge vs B&H | Beat B&H |
|---|---|---|---|
| lowest | 0.16 … 0.24 | -32.4% | 16% |
| Q2 | 0.24 … 0.27 | -30.5% | 25% |
| Q3 | 0.27 … 0.32 | -34.5% | 25% |
| Q4 | 0.32 … 0.39 | -39.5% | 32% |
| highest | 0.39 … 1.12 | -44.2% | 35% |

**Past total return** — rank correlation with edge: -0.74

| Quintile | Trait range | Mean edge vs B&H | Beat B&H |
|---|---|---|---|
| lowest | -0.85 … -0.15 | +16.7% | 75% |
| Q2 | -0.15 … 0.19 | -1.1% | 32% |
| Q3 | 0.19 … 0.56 | -33.7% | 12% |
| Q4 | 0.57 … 1.23 | -43.3% | 9% |
| highest | 1.23 … 21.68 | -119.8% | 5% |

**Past worst drawdown** — rank correlation with edge: -0.54

| Quintile | Trait range | Mean edge vs B&H | Beat B&H |
|---|---|---|---|
| lowest | -0.99 … -0.61 | +27.2% | 67% |
| Q2 | -0.60 … -0.49 | -31.3% | 40% |
| Q3 | -0.49 … -0.41 | -45.4% | 18% |
| Q4 | -0.41 … -0.33 | -64.0% | 8% |
| highest | -0.33 … -0.17 | -67.7% | 0% |

**SMA200 crossings / year** — rank correlation with edge: -0.31

| Quintile | Trait range | Mean edge vs B&H | Beat B&H |
|---|---|---|---|
| lowest | 2.01 … 6.22 | +2.6% | 53% |
| Q2 | 6.42 … 8.02 | -38.5% | 33% |
| Q3 | 8.22 … 9.63 | -43.2% | 25% |
| Q4 | 9.83 … 11.63 | -51.4% | 13% |
| highest | 11.83 … 19.26 | -54.7% | 5% |

## 2. Predictive view — traits from 2016-2021, edge from 2021-2026 (493 tickers)

**Volatility (annualized)** — rank correlation with edge: -0.21

| Quintile | Trait range | Mean edge vs B&H | Beat B&H |
|---|---|---|---|
| lowest | 0.19 … 0.26 | -17.6% | 33% |
| Q2 | 0.26 … 0.29 | -25.8% | 28% |
| Q3 | 0.29 … 0.33 | -38.8% | 21% |
| Q4 | 0.33 … 0.39 | -51.6% | 26% |
| highest | 0.40 … 0.82 | -54.1% | 24% |

**Past total return** — rank correlation with edge: +0.07

| Quintile | Trait range | Mean edge vs B&H | Beat B&H |
|---|---|---|---|
| lowest | -0.84 … 0.21 | -39.2% | 21% |
| Q2 | 0.21 … 0.68 | -50.7% | 23% |
| Q3 | 0.69 … 1.31 | -37.6% | 23% |
| Q4 | 1.31 … 2.23 | -37.9% | 31% |
| highest | 2.25 … 48.04 | -22.6% | 33% |

**Past worst drawdown** — rank correlation with edge: +0.23

| Quintile | Trait range | Mean edge vs B&H | Beat B&H |
|---|---|---|---|
| lowest | -0.95 … -0.60 | -45.6% | 17% |
| Q2 | -0.60 … -0.50 | -55.8% | 23% |
| Q3 | -0.50 … -0.43 | -35.4% | 27% |
| Q4 | -0.43 … -0.35 | -30.8% | 31% |
| highest | -0.35 … -0.22 | -20.4% | 33% |

**SMA200 crossings / year** — rank correlation with edge: -0.01

| Quintile | Trait range | Mean edge vs B&H | Beat B&H |
|---|---|---|---|
| lowest | 0.48 … 5.40 | -25.0% | 30% |
| Q2 | 5.43 … 6.80 | -41.9% | 22% |
| Q3 | 7.00 … 8.21 | -51.1% | 26% |
| Q4 | 8.41 … 9.81 | -42.7% | 29% |
| highest | 10.01 … 17.61 | -28.8% | 23% |

Hindsight correlations explain; only predictive correlations are tradeable.
