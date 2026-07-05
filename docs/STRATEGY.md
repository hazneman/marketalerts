# Strategy backtest — SMA200 trend filter, 2-day confirmation, last 5 years

Buy after 2 consecutive closes above the SMA200, sell after 2 consecutive closes below; execution at next day's open. Per-ticker, all-in/all-out, vs buy-and-hold of the same ticker. 500 tickers (today's index members — survivorship bias applies to both sides).

| Metric | Strategy | Buy & hold |
|---|---|---|
| Mean total return | +46.4% | +85.0% |
| Median total return | +5.0% | +37.4% |
| Average max drawdown | -39.5% | -47.0% |

- Strategy beat buy-and-hold on **25%** of tickers
- 6846 round trips (~13.7 per ticker, ~2.7/yr)
- Trade win rate 25%, average trade +3.8%, median trade -2.4%
- Average time in market: 59% of days
