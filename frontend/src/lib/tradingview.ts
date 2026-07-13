export function tradingViewUrl(ticker: string): string {
  // Yahoo suffixes -> TradingView exchange prefixes
  const symbol = ticker.endsWith('.IS')
    ? `BIST:${ticker.slice(0, -3)}`
    : ticker.endsWith('.DE')
      ? `XETR:${ticker.slice(0, -3)}`
      : ticker
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`
}
