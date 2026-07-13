import { tradingViewUrl } from '../lib/tradingview'
import type { AlertItem } from '../types'
import { MARKET_BADGE_STYLES, MARKET_LABELS } from '../types'
import DirectionBadge from './DirectionBadge'

export function MarketBadge({ market }: { market?: string }) {
  if (!market) return null
  return (
    <span
      className={`ml-1.5 inline-block rounded px-1 py-px align-middle text-[10px] font-semibold tracking-wide ring-1 ${
        MARKET_BADGE_STYLES[market] ?? 'bg-slate-500/10 text-slate-400 ring-white/10'
      }`}
    >
      {MARKET_LABELS[market] ?? market.toUpperCase()}
    </span>
  )
}

function fmtPx(v: number): string {
  return Math.abs(v) >= 10 ? v.toFixed(2) : v.toFixed(4)
}

const VERDICT_STYLES: Record<string, string> = {
  buy: 'bg-emerald-500/15 text-emerald-400',
  hold: 'bg-amber-500/15 text-amber-400',
  sell: 'bg-rose-500/15 text-rose-400',
}

function VerdictBadge({ a }: { a: AlertItem }) {
  if (!a.verdict) return <span className="text-slate-500">—</span>
  const fund = a.fundamentals
    ? `Fundamentals ${a.fundamentals.rating} (${a.fundamentals.score >= 0 ? '+' : ''}${a.fundamentals.score})`
    : 'Fundamentals unavailable'
  const macd = a.macd_confirms ? 'MACD confirms' : 'MACD against'
  return (
    <span
      title={`${a.verdict_reason ?? ''} · ${macd} · ${fund}`}
      className={`inline-block cursor-help rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase ${VERDICT_STYLES[a.verdict]}`}
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

export default function AlertTable({ alerts }: { alerts: AlertItem[] }) {
  const hasSma50 = alerts.some((a) => a.values.sma50 !== undefined)
  const hasRsi = alerts.some((a) => a.values.rsi !== undefined)
  const hasVerdict = alerts.some((a) => a.verdict !== undefined)
  return (
    <div className="overflow-x-auto rounded-xl bg-slate-900/30 ring-1 ring-white/5">
      <table className="w-full text-left text-sm">
        <thead className="bg-white/[0.03] text-[11px] font-medium uppercase tracking-wider text-slate-500">
          <tr>
            <th className="px-4 py-2.5">Signal</th>
            <th className="px-4 py-2.5">Ticker</th>
            <th className="px-4 py-2.5">Date</th>
            <th className="px-4 py-2.5 text-right">Close</th>
            {hasRsi && <th className="px-4 py-2.5 text-right">RSI</th>}
            {hasSma50 && <th className="px-4 py-2.5 text-right">SMA 50</th>}
            <th className="px-4 py-2.5 text-right">SMA 200</th>
            <th className="px-4 py-2.5 text-right">vs SMA 200</th>
            {hasVerdict && <th className="px-4 py-2.5">Verdict</th>}
          </tr>
        </thead>
        <tbody className="tnum divide-y divide-white/5">
          {alerts.map((a) => (
            <tr key={`${a.rule}-${a.ticker}`} className="transition-colors hover:bg-white/[0.03]">
              <td className="px-4 py-2.5">
                <DirectionBadge direction={a.direction} />
              </td>
              <td className="px-4 py-2.5">
                <a
                  href={tradingViewUrl(a.ticker)}
                  target="_blank"
                  rel="noreferrer"
                  title="Open in TradingView"
                  className="font-semibold text-sky-400 hover:text-sky-300 hover:underline"
                >
                  {a.ticker} ↗
                </a>
                <MarketBadge market={a.market} />
              </td>
              <td className="px-4 py-2.5 text-slate-400">{a.date}</td>
              <td className="px-4 py-2.5 text-right font-medium text-slate-100">
                {fmtPx(a.close)}
              </td>
              {hasRsi && (
                <td className="px-4 py-2.5 text-right text-amber-400">
                  {a.values.rsi?.toFixed(1) ?? '—'}
                </td>
              )}
              {hasSma50 && (
                <td className="px-4 py-2.5 text-right text-slate-300">
                  {a.values.sma50 !== undefined ? fmtPx(a.values.sma50) : '—'}
                </td>
              )}
              <td className="px-4 py-2.5 text-right text-slate-300">
                {a.values.sma200 !== undefined ? fmtPx(a.values.sma200) : '—'}
              </td>
              <td
                className={`px-4 py-2.5 text-right ${
                  a.close >= (a.values.sma200 ?? 0) ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {pctFromSma200(a) ?? '—'}
              </td>
              {hasVerdict && (
                <td className="px-4 py-2.5">
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
