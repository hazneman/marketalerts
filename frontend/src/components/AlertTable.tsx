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

export default function AlertTable({ alerts }: { alerts: AlertItem[] }) {
  const hasSma50 = alerts.some((a) => a.values.sma50 !== undefined)
  const hasRsi = alerts.some((a) => a.values.rsi !== undefined)
  const hasVerdict = alerts.some((a) => a.verdict !== undefined)
  const hasFib = alerts.some((a) => a.fib?.daily)
  const hasVol = alerts.some((a) => a.volume)
  return (
    <div className={tableWrapCls}>
      <table className="w-full text-left text-[13px]">
        <thead className={theadCls}>
          <tr>
            <th className={cellCls}>Signal</th>
            <th className={cellCls}>Ticker</th>
            <th className={cellCls}>Date</th>
            <th className={`${cellCls} text-right`}>Close</th>
            {hasRsi && <th className={`${cellCls} text-right`}>RSI</th>}
            {hasSma50 && <th className={`${cellCls} text-right`}>SMA 50</th>}
            <th className={`${cellCls} text-right`}>SMA 200</th>
            <th className={`${cellCls} text-right`}>vs SMA 200</th>
            {hasFib && <th className={cellCls}>Fib (D)</th>}
            {hasVol && <th className={`${cellCls} text-right`}>Vol</th>}
            {hasVerdict && <th className={cellCls}>Verdict</th>}
          </tr>
        </thead>
        <tbody className={`tnum divide-y divide-hair`}>
          {alerts.map((a) => (
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
                  className="font-semibold text-accent hover:underline"
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
