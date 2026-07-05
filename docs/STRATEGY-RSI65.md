# Strategy backtest — SMA200 trend filter, 2-day confirmation, RSI≤65 entry filter, last 5 years

Buy after 2 consecutive closes above the SMA200, sell after 2 consecutive closes below; execution at next day's open. Entries are skipped while RSI(14) > 65. Per-ticker, all-in/all-out, vs buy-and-hold of the same ticker. 490 tickers (today's index members — survivorship bias applies to both sides).

| Metric | Strategy | Buy & hold |
|---|---|---|
| Mean total return | +47.3% | +85.6% |
| Median total return | +5.4% | +37.4% |
| Average max drawdown | -38.9% | -46.9% |

- Strategy beat buy-and-hold on **25%** of tickers
- 6468 round trips (~13.2 per ticker, ~2.6/yr)
- Trade win rate 26%, average trade +3.9%, median trade -2.4%
- Average time in market: 57% of days
