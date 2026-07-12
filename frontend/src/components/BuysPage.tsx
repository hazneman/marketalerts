import { useAlerts } from '../hooks/useAlerts'
import type { AlertItem } from '../types'
import { CATEGORY_LABELS } from '../types'

const FACTOR_LABELS: Record<string, { label: string; fmt: (m: Record<string, number>) => string }> = {
  analyst: {
    label: 'Analyst consensus',
    fmt: (m) => (m.rec_mean !== undefined ? `${m.rec_mean.toFixed(1)} (1=strong buy … 5=sell)` : '—'),
  },
  valuation: {
    label: 'Valuation (forward P/E)',
    fmt: (m) => (m.forward_pe !== undefined ? `${m.forward_pe.toFixed(1)}×` : '—'),
  },
  fcf_yield: {
    label: 'Free-cash-flow yield',
    fmt: (m) => (m.fcf_yield_pct !== undefined ? `${m.fcf_yield_pct.toFixed(1)}%` : '—'),
  },
  target_upside: {
    label: 'Analyst target upside',
    fmt: (m) =>
      m.target_upside_pct !== undefined
        ? `${m.target_upside_pct >= 0 ? '+' : ''}${m.target_upside_pct.toFixed(1)}%`
        : '—',
  },
  earnings_growth: {
    label: 'Earnings growth',
    fmt: (m) =>
      m.earnings_growth_pct !== undefined
        ? `${m.earnings_growth_pct >= 0 ? '+' : ''}${m.earnings_growth_pct.toFixed(1)}%`
        : '—',
  },
}

function FactorChip({ value }: { value: number | undefined }) {
  if (value === undefined)
    return <span className="rounded-full bg-slate-500/15 px-2 py-0.5 text-xs text-slate-500">n/a</span>
  const style =
    value > 0
      ? 'bg-emerald-500/15 text-emerald-400'
      : value < 0
        ? 'bg-rose-500/15 text-rose-400'
        : 'bg-slate-500/15 text-slate-400'
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${style}`}>
      {value > 0 ? '+1' : value < 0 ? '−1' : '0'}
    </span>
  )
}

function BuyCard({ a }: { a: AlertItem }) {
  const f = a.fundamentals
  const pct = a.values.sma200 ? ((a.close - a.values.sma200) / a.values.sma200) * 100 : null
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-3">
          <a
            href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(a.ticker)}`}
            target="_blank"
            rel="noreferrer"
            className="text-lg font-bold text-sky-400 hover:text-sky-300 hover:underline"
          >
            {a.ticker} ↗
          </a>
          <span className="text-sm text-slate-400">{CATEGORY_LABELS[a.category] ?? a.category}</span>
        </div>
        <div className="text-sm text-slate-300">
          {a.close >= 10 ? a.close.toFixed(2) : a.close.toFixed(4)}
          {pct !== null && (
            <span className={`ml-2 ${pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {pct >= 0 ? '+' : ''}
              {pct.toFixed(2)}% vs SMA200
            </span>
          )}
          <span className="ml-2 text-slate-500">{a.date}</span>
        </div>
      </div>

      <p className="mt-1 text-sm text-slate-400">
        {a.verdict_reason} · <span className="text-emerald-400">MACD confirms</span>
      </p>

      {f ? (
        <div className="mt-3 rounded-md border border-slate-800/70 bg-slate-900/50 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm">
            <span className="font-medium text-slate-200">Fundamentals</span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase ${
                f.rating === 'strong'
                  ? 'bg-emerald-500/15 text-emerald-400'
                  : f.rating === 'weak'
                    ? 'bg-rose-500/15 text-rose-400'
                    : 'bg-slate-500/15 text-slate-300'
              }`}
            >
              {f.rating} ({f.score >= 0 ? '+' : ''}
              {f.score})
            </span>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(FACTOR_LABELS).map(([key, def]) => (
                <tr key={key}>
                  <td className="py-1 text-slate-400">{def.label}</td>
                  <td className="py-1 text-right text-slate-200">{def.fmt(f.metrics ?? {})}</td>
                  <td className="w-12 py-1 text-right">
                    <FactorChip value={f.factors?.[key]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          Fundamentals unavailable for this ticker — verdict is technicals + MACD only.
        </p>
      )}
    </div>
  )
}

export default function BuysPage() {
  const { latest, error } = useAlerts()

  if (error) {
    return (
      <p className="rounded-lg border border-dashed border-slate-800 px-4 py-6 text-center text-sm text-slate-500">
        No scan data yet.
      </p>
    )
  }
  if (!latest) return <p className="py-8 text-center text-slate-500">Loading…</p>

  const buys = latest.alerts.filter((a) => a.verdict === 'buy')

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-100">
          BUY verdicts — {latest.bar_date}
        </h2>
        <span className="text-sm text-slate-500">
          {buys.length} of {latest.alerts.length} alerts passed all three layers
        </span>
      </div>

      {buys.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {buys.map((a) => (
            <BuyCard key={`${a.rule}-${a.ticker}`} a={a} />
          ))}
        </div>
      ) : (
        <p className="rounded-lg border border-dashed border-slate-800 px-4 py-6 text-center text-sm text-slate-500">
          No BUY verdicts on {latest.bar_date} — signal, MACD, and fundamentals did not align on any name.
        </p>
      )}

      <p className="text-xs text-slate-500">
        A BUY requires all three layers to agree: a bullish signal, MACD momentum
        confirmation, and fundamentals that are not weak. Factor chips: +1 favorable
        · 0 neutral · −1 unfavorable. Informational, not investment advice.
      </p>
    </section>
  )
}
