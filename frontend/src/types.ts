export interface AlertItem {
  ticker: string
  rule: string
  category: string
  direction: 'bullish' | 'bearish'
  date: string
  close: number
  values: Record<string, number>
  market?: 'us' | 'bist'
  verdict?: 'buy' | 'hold' | 'sell'
  verdict_reason?: string
  macd_confirms?: boolean
  fundamentals?: Fundamentals | null
}

export const MARKET_LABELS: Record<string, string> = {
  us: 'US',
  bist: 'BIST',
}

export interface Fundamentals {
  score: number
  rating: 'strong' | 'neutral' | 'weak'
  factors?: Record<string, number>
  metrics?: Record<string, number>
  analyst?: {
    n_analysts?: number
    consensus?: string
    target_low?: number
    target_mean?: number
    target_high?: number
    price?: number
  } | null
  rating_changes?: {
    date: string
    firm: string
    action: string
    from_grade: string | null
    to_grade: string
  }[]
}

export interface ScanResult {
  schema_version: number
  generated_at: string
  bar_date: string
  bar_dates?: Record<string, string>
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

export interface ForexOutlook {
  rate_6m: string
  call: 'long' | 'short' | 'neutral' | 'benchmark'
  rationale: string
}

export interface ForexCurrency {
  code: string
  country: string
  bank: string
  rate: number
  change_bps: number
  changed_on: string
  carry_vs_usd: number
  outlook: ForexOutlook | null
  vs_usd: {
    price: number
    sma200: number
    above_sma200: boolean
    chg_1m_pct: number
  } | null
  suggestion: string
}

export interface ForexPair {
  symbol: string
  price: number
  sma200: number
  above_sma200: boolean
  vs_sma200_pct: number
  chg_1m_pct: number
  carry_pct?: number
  alignment?: 'aligned_bull' | 'aligned_bear' | 'conflict' | 'trend_only'
  comment?: string
}

export interface ForexData {
  schema_version: number
  generated_at: string
  bar_date: string | null
  rates_as_of: string
  outlook_as_of?: string
  usd_rate: number
  currencies: ForexCurrency[]
  pairs?: ForexPair[]
  pair_alerts?: AlertItem[]
}

export const CATEGORY_LABELS: Record<string, string> = {
  price_sma200: 'Price × SMA 200 crosses',
  sma50_sma200: 'Golden / Death crosses (SMA 50 × SMA 200)',
  price_sma200_weekly: '200-week SMA crosses (secular trend)',
  rsi_extended: 'RSI > 75 — extended, consider trimming',
}
