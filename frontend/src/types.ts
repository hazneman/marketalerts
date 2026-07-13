export interface AlertItem {
  ticker: string
  rule: string
  category: string
  direction: 'bullish' | 'bearish'
  date: string
  close: number
  values: Record<string, number>
  market?: 'us' | 'de' | 'bist'
  verdict?: 'buy' | 'hold' | 'sell'
  verdict_reason?: string
  macd_confirms?: boolean
  fundamentals?: Fundamentals | null
  sector?: {
    name: string
    symbol: string
    state: 'leading' | 'improving' | 'weakening' | 'lagging' | null
    factor: number
  } | null
}

export const MARKET_LABELS: Record<string, string> = {
  us: 'US',
  de: 'DE',
  bist: 'BIST',
}

export const MARKET_ORDER: Record<string, number> = { us: 0, de: 1, bist: 2 }

export const MARKET_BADGE_STYLES: Record<string, string> = {
  us: 'bg-sky-500/10 text-sky-300 ring-sky-400/20',
  de: 'bg-violet-500/10 text-violet-300 ring-violet-400/20',
  bist: 'bg-amber-500/10 text-amber-300 ring-amber-400/20',
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

export interface SectorRow {
  symbol: string
  name: string
  price: number
  above_sma200: boolean
  vs_sma200_pct: number
  chg: Record<string, number | null>
  rs: Record<string, number>
  rs_score: number
  rank: number
  state: 'leading' | 'improving' | 'weakening' | 'lagging'
  comment: string
}

export interface SectorData {
  schema_version: number
  generated_at: string
  bar_date: string
  benchmark: { symbol: string; chg: Record<string, number | null> }
  sectors: SectorRow[]
}

export const SECTOR_HORIZONS = ['1w', '1m', '3m', '6m', '1y'] as const

export const SECTOR_STATE: Record<string, { label: string; style: string }> = {
  leading: { label: 'Leading', style: 'bg-emerald-500/15 text-emerald-300 ring-emerald-400/25' },
  improving: { label: 'Improving', style: 'bg-sky-500/15 text-sky-300 ring-sky-400/25' },
  weakening: { label: 'Weakening', style: 'bg-amber-500/15 text-amber-300 ring-amber-400/25' },
  lagging: { label: 'Lagging', style: 'bg-rose-500/15 text-rose-300 ring-rose-400/25' },
}

export const CATEGORY_LABELS: Record<string, string> = {
  price_sma200: 'Price × SMA 200 crosses',
  sma50_sma200: 'Golden / Death crosses (SMA 50 × SMA 200)',
  price_sma200_weekly: '200-week SMA crosses (secular trend)',
  rsi_extended: 'RSI > 75 — extended, consider trimming',
}
