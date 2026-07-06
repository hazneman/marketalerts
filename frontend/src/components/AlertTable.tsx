import type { AlertItem } from '../types'
import DirectionBadge from './DirectionBadge'

function tradingViewUrl(ticker: string): string {
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ticker)}`
}

function fmtPx(v: number): string {
  return Math.abs(v) >= 10 ? v.toFixed(2) : v.toFixed(4)
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
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-4 py-2.5">Signal</th>
            <th className="px-4 py-2.5">Ticker</th>
            <th className="px-4 py-2.5">Date</th>
            <th className="px-4 py-2.5 text-right">Close</th>
            {hasRsi && <th className="px-4 py-2.5 text-right">RSI</th>}
            {hasSma50 && <th className="px-4 py-2.5 text-right">SMA 50</th>}
            <th className="px-4 py-2.5 text-right">SMA 200</th>
            <th className="px-4 py-2.5 text-right">vs SMA 200</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {alerts.map((a) => (
            <tr key={`${a.rule}-${a.ticker}`} className="bg-slate-950 hover:bg-slate-900/60">
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
