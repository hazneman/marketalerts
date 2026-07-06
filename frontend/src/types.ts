export interface AlertItem {
  ticker: string
  rule: string
  category: string
  direction: 'bullish' | 'bearish'
  date: string
  close: number
  values: Record<string, number>
}

export interface ScanResult {
  schema_version: number
  generated_at: string
  bar_date: string
  universe_count: number
  scanned: number
  failures: string[]
  insufficient_history: string[]
  alerts: AlertItem[]
}

export interface HistoryDay {
  bar_date: string
  generated_at: string
  scanned: number
  alerts: AlertItem[]
}

export interface AlertHistory {
  schema_version: number
  days: HistoryDay[]
}

export const CATEGORY_LABELS: Record<string, string> = {
  price_sma200: 'Price × SMA 200 crosses',
  sma50_sma200: 'Golden / Death crosses (SMA 50 × SMA 200)',
  price_sma200_weekly: '200-week SMA crosses (secular trend)',
}
