export function tradingViewUrl(ticker: string): string {
  // BIST tickers carry Yahoo's .IS suffix; TradingView wants BIST:SYMBOL
  const symbol = ticker.endsWith('.IS') ? `BIST:${ticker.slice(0, -3)}` : ticker
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`
}
