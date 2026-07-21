import { useMemo, useState } from 'react'
import { badgeFlat, badgeRing, cellCls, rowCls, tableWrapCls, theadCls, type Tone } from '../lib/ui'
import { tradingViewUrl } from '../lib/tradingview'
import type { AlertItem } from '../types'
import { MARKET_LABELS, MARKET_TONES } from '../types'
import DirectionBadge from './DirectionBadge'

export function MarketBadge({ market }: { market?: string }) {
  if (!market) return null
  const tone = MARKET_TONES[market] ?? 'neutral'
  return (
    <span
      className={`ml-1.5 inline-block rounded px-1 py-px align-middle text-[10px] font-semibold tracking-wide ${badgeRing[tone]}`}
    >
      {MARKET_LABELS[market] ?? market.toUpperCase()}
    </span>
  )
}

function fmtPx(v: number): string {
  return Math.abs(v) >= 10 ? v.toFixed(2) : v.toFixed(4)
}

const VERDICT_TONES: Record<string, Tone> = { buy: 'up', hold: 'accent', sell: 'down' }

function VerdictBadge({ a }: { a: AlertItem }) {
  if (!a.verdict) return <span className="text-muted">—</span>
  const fund = a.fundamentals
    ? `Fundamentals ${a.fundamentals.rating} (${a.fundamentals.score >= 0 ? '+' : ''}${a.fundamentals.score})`
    : 'Fundamentals unavailable'
  const macd = a.macd_confirms ? 'MACD confirms' : 'MACD against'
  return (
    <span
      title={`${a.verdict_reason ?? ''} · ${macd} · ${fund}`}
      className={`inline-block cursor-help rounded px-2 py-0.5 text-xs font-semibold uppercase ${badgeFlat[VERDICT_TONES[a.verdict] ?? 'neutral']}`}
    >
      {a.verdict}
    </span>
  )
}

function pctFromSma200(a: AlertItem): string | null {
  const sma200 = a.values.sma200
  if (!sma200) return null
  const pct = ((a.close - sma200) / sma200) * 100
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
}

// Nearest daily Fibonacci level: "61.8% +1.2%" (near a level = tighter |dist|).
function NearestFib({ a }: { a: AlertItem }) {
  const d = a.fib?.daily
  if (!d) return <span className="text-faint">—</span>
  const { label, dist_pct } = d.nearest
  const near = Math.abs(dist_pct) <= 1.5 // sitting right on the level
  return (
    <span className={near ? 'text-info' : 'text-ink-2'}>
      {label}{' '}
      <span className={dist_pct >= 0 ? 'text-up' : 'text-down'}>
        {dist_pct >= 0 ? '+' : ''}
        {dist_pct.toFixed(1)}%
      </span>
    </span>
  )
}

// ---- Sorting -------------------------------------------------------------
// Each column exposes a numeric or string key; undefined values always sink to
// the bottom regardless of direction, so blanks never crowd out real data.
type SortDir = 'asc' | 'desc'
type SortKey = 'ticker' | 'date' | 'close' | 'rsi' | 'sma50' | 'sma200' | 'vs200' | 'vol'

const SORT_ACCESSORS: Record<SortKey, (a: AlertItem) => number | string | undefined> = {
  ticker: (a) => a.ticker,
  date: (a) => a.date,
  close: (a) => a.close,
  rsi: (a) => a.values.rsi,
  sma50: (a) => a.values.sma50,
  sma200: (a) => a.values.sma200,
  vs200: (a) => (a.values.sma200 ? (a.close - a.values.sma200) / a.values.sma200 : undefined),
  vol: (a) => a.volume?.ratio,
}

// Text columns read most naturally A→Z; numbers/dates most-relevant-first.
const DEFAULT_DIR: Record<SortKey, SortDir> = {
  ticker: 'asc', date: 'desc', close: 'desc', rsi: 'desc',
  sma50: 'desc', sma200: 'desc', vs200: 'desc', vol: 'desc',
}

function SortHeader({
  label, col, active, dir, onSort, align = 'left',
}: {
  label: string
  col: SortKey
  active: boolean
  dir: SortDir
  onSort: (c: SortKey) => void
  align?: 'left' | 'right'
}) {
  return (
    <th
      className={`${cellCls} ${align === 'right' ? 'text-right' : ''}`}
      aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button
        type="button"
        onClick={() => onSort(col)}
        className={`inline-flex items-center gap-1 hover:text-ink ${
          align === 'right' ? 'flex-row-reverse' : ''
        } ${active ? 'text-ink' : ''}`}
      >
        {label}
        <span className={`text-[10px] ${active ? 'text-accent' : 'text-faint'}`}>
          {active ? (dir === 'asc' ? '▲' : '▼') : '↕'}
        </span>
      </button>
    </th>
  )
}

export default function AlertTable({ alerts }: { alerts: AlertItem[] }) {
  const hasSma50 = alerts.some((a) => a.values.sma50 !== undefined)
  const hasRsi = alerts.some((a) => a.values.rsi !== undefined)
  const hasVerdict = alerts.some((a) => a.verdict !== undefined)
  const hasFib = alerts.some((a) => a.fib?.daily)
  const hasVol = alerts.some((a) => a.volume)

  // Default view: latest alerts first.
  const [sortKey, setSortKey] = useState<SortKey>('date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const onSort = (col: SortKey) => {
    if (col === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(col)
      setSortDir(DEFAULT_DIR[col])
    }
  }

  const sorted = useMemo(() => {
    const get = SORT_ACCESSORS[sortKey]
    const factor = sortDir === 'asc' ? 1 : -1
    return [...alerts].sort((a, b) => {
      const va = get(a)
      const vb = get(b)
      // undefined always sinks, independent of direction
      if (va === undefined && vb === undefined) return 0
      if (va === undefined) return 1
      if (vb === undefined) return -1
      if (va < vb) return -1 * factor
      if (va > vb) return 1 * factor
      return 0
    })
  }, [alerts, sortKey, sortDir])

  return (
    <div className={tableWrapCls}>
      <table className="w-full text-left text-[13px]">
        <thead className={theadCls}>
          <tr>
            <th className={cellCls}>Signal</th>
            <SortHeader label="Ticker" col="ticker" active={sortKey === 'ticker'} dir={sortDir} onSort={onSort} />
            <SortHeader label="Date" col="date" active={sortKey === 'date'} dir={sortDir} onSort={onSort} />
            <SortHeader label="Close" col="close" active={sortKey === 'close'} dir={sortDir} onSort={onSort} align="right" />
            {hasRsi && <SortHeader label="RSI" col="rsi" active={sortKey === 'rsi'} dir={sortDir} onSort={onSort} align="right" />}
            {hasSma50 && <SortHeader label="SMA 50" col="sma50" active={sortKey === 'sma50'} dir={sortDir} onSort={onSort} align="right" />}
            <SortHeader label="SMA 200" col="sma200" active={sortKey === 'sma200'} dir={sortDir} onSort={onSort} align="right" />
            <SortHeader label="vs SMA 200" col="vs200" active={sortKey === 'vs200'} dir={sortDir} onSort={onSort} align="right" />
            {hasFib && <th className={cellCls}>Fib (D)</th>}
            {hasVol && <SortHeader label="Vol" col="vol" active={sortKey === 'vol'} dir={sortDir} onSort={onSort} align="right" />}
            {hasVerdict && <th className={cellCls}>Verdict</th>}
          </tr>
        </thead>
        <tbody className={`tnum divide-y divide-hair`}>
          {sorted.map((a) => (
            <tr key={`${a.rule}-${a.ticker}`} className={rowCls}>
              <td className={cellCls}>
                <DirectionBadge direction={a.direction} />
              </td>
              <td className={cellCls}>
                <a
                  href={tradingViewUrl(a.ticker)}
                  target="_blank"
                  rel="noreferrer"
                  title="Open in TradingView"
                  className="font-semibold text-info hover:underline"
                >
                  {a.ticker} ↗
                </a>
                <MarketBadge market={a.market} />
              </td>
              <td className={`${cellCls} text-muted`}>{a.date}</td>
              <td className={`${cellCls} text-right font-medium text-ink`}>
                {fmtPx(a.close)}
              </td>
              {hasRsi && (
                <td className={`${cellCls} text-right text-accent`}>
                  {a.values.rsi?.toFixed(1) ?? '—'}
                </td>
              )}
              {hasSma50 && (
                <td className={`${cellCls} text-right text-ink-2`}>
                  {a.values.sma50 !== undefined ? fmtPx(a.values.sma50) : '—'}
                </td>
              )}
              <td className={`${cellCls} text-right text-ink-2`}>
                {a.values.sma200 !== undefined ? fmtPx(a.values.sma200) : '—'}
              </td>
              <td
                className={`${cellCls} text-right ${
                  a.close >= (a.values.sma200 ?? 0) ? 'text-up' : 'text-down'
                }`}
              >
                {pctFromSma200(a) ?? '—'}
              </td>
              {hasFib && (
                <td className={cellCls}>
                  <NearestFib a={a} />
                </td>
              )}
              {hasVol && (
                <td
                  className={`${cellCls} text-right ${
                    a.volume ? (a.volume.above_avg ? 'text-up' : 'text-muted') : 'text-faint'
                  }`}
                >
                  {a.volume ? `${a.volume.ratio.toFixed(1)}×` : '—'}
                </td>
              )}
              {hasVerdict && (
                <td className={cellCls}>
                  <VerdictBadge a={a} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
