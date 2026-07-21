import type { Tone } from './lib/ui'

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
  fib?: { daily: FibFrame | null; weekly: FibFrame | null } | null
  volume?: VolumeSignal | null
}

export interface FibLevel {
  label: string
  price: number
  dist_pct: number
}

export interface FibFrame {
  high: number
  low: number
  position_pct: number
  levels: FibLevel[]
  nearest: FibLevel
}

export interface VolumeSignal {
  today: number
  avg20: number
  ratio: number
  above_avg: boolean
}

export interface PricesData {
  schema_version: number
  generated_at: string
  bar_dates: Record<string, string>
  prices: Record<string, { close: number; chg_1d_pct: number | null }>
}

export const MARKET_LABELS: Record<string, string> = {
  us: 'US',
  de: 'DE',
  bist: 'BIST',
}

export const MARKET_ORDER: Record<string, number> = { us: 0, de: 1, bist: 2 }

export const MARKET_TONES: Record<string, Tone> = { us: 'info', de: 'de', bist: 'accent' }

export interface Fundamentals {
  score: number
  rating: 'strong' | 'neutral' | 'weak'
  factors?: Record<string, number>
  metrics?: Record<string, number>
  // Display-only enrichment (NOT part of the verdict score):
  profile?: Record<string, number>
  flags?: string[]
  coverage?: { present: number; total: number }
  summary?: string
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

export interface SectorConstituent {
  ticker: string
  name: string
  cap: number
  price: number
  chg_1d_pct: number | null
  fundamentals?: {
    score: number
    rating: 'strong' | 'neutral' | 'weak'
    forward_pe?: number
    div_yield_pct?: number
    rev_growth_pct?: number
    margin_pct?: number
    consensus?: string
    target_upside_pct?: number
  } | null
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
  top?: SectorConstituent[]
}

export interface SectorData {
  schema_version: number
  generated_at: string
  bar_date: string
  benchmark: { symbol: string; chg: Record<string, number | null> }
  sectors: SectorRow[]
}

export interface TrackRecordEntry {
  id: string
  ticker: string
  market: string
  category: string
  rule: string
  direction: string
  verdict: string
  entry_date: string
  entry_price: number
  benchmark: string | null
  entry_bench_close: number | null
  last_date: string | null
  last_price: number | null
  stock_return_pct: number | null
  bench_return_pct: number | null
  excess_pct: number | null
  success: boolean | null
  days_held: number
  status: 'open' | 'matured'
  target_mean?: number | null
  target_reached?: boolean | null
}

export interface TrackRecordData {
  schema_version: number
  generated_at: string
  bar_date: string
  benchmarks: Record<string, { symbol: string; last_date: string; last_close: number }>
  entries: TrackRecordEntry[]
}

export interface TickerHealth {
  close: number
  sma200?: number
  vs_sma200_pct?: number
  sma50?: number
  vs_sma50_pct?: number
  rsi?: number
  macd_bullish?: boolean
  chg_20d_pct?: number
  peak_252d?: number
  drawdown_pct?: number
  sector_state?: string
  recent_warnings?: { date: string; category: string; rule: string; direction: string }[]
}

export interface HealthData {
  schema_version: number
  generated_at: string
  bar_date: string
  warn_days: number
  tickers: Record<string, TickerHealth>
}

export interface TargetsData {
  schema_version: number
  generated_at: string
  targets: Record<string, { target_mean: number | null; n_analysts?: number; as_of: string }>
}

// Short label for a benchmark index symbol (shown as "vs DAX" etc.)
export const BENCHMARK_LABELS: Record<string, string> = {
  SPY: 'S&P 500',
  '^GDAXI': 'DAX',
  'XU100.IS': 'BIST 100',
}

export const SECTOR_HORIZONS = ['1w', '1m', '3m', '6m', '1y'] as const

export const SECTOR_STATE: Record<string, { label: string; tone: Tone }> = {
  leading: { label: 'Leading', tone: 'up' },
  improving: { label: 'Improving', tone: 'info' },
  weakening: { label: 'Weakening', tone: 'accent' },
  lagging: { label: 'Lagging', tone: 'down' },
}

export const CONSENSUS_LABELS: Record<string, { label: string; tone: Tone }> = {
  strong_buy: { label: 'Strong buy', tone: 'up' },
  buy: { label: 'Buy', tone: 'up' },
  hold: { label: 'Hold', tone: 'accent' },
  underperform: { label: 'Underperform', tone: 'down' },
  sell: { label: 'Sell', tone: 'down' },
}

export const CATEGORY_LABELS: Record<string, string> = {
  price_sma200: 'Price × SMA 200 crosses',
  sma50_sma200: 'Golden / Death crosses (SMA 50 × SMA 200)',
  price_sma200_weekly: '200-week SMA crosses (secular trend)',
  rsi_extended: 'RSI > 75 — extended, consider trimming',
}
