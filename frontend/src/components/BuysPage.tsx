import { useState } from 'react'
import { useAlerts, usePortfolio } from '../hooks/useAlerts'
import { addPosition } from '../lib/portfolio'
import { tradingViewUrl } from '../lib/tradingview'
import type { AlertItem, FibFrame, Fundamentals } from '../types'
import { CATEGORY_LABELS, SECTOR_STATE } from '../types'
import { MarketBadge } from './AlertTable'

const inputCls =
  'rounded-lg bg-white/[0.04] px-2 py-1 text-xs text-slate-100 placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-sky-400/40'

function AddToPortfolio({ a }: { a: AlertItem }) {
  const { positions } = usePortfolio()
  const [open, setOpen] = useState(false)
  const [shares, setShares] = useState('')
  const [cost, setCost] = useState(String(a.close))
  const [date, setDate] = useState(a.date)
  const held = positions.some((p) => p.ticker === a.ticker)

  if (held && !open) {
    return (
      <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300 ring-1 ring-emerald-400/20">
        ✓ in portfolio
      </span>
    )
  }
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-full bg-sky-500/15 px-2.5 py-1 text-xs font-medium text-sky-300 ring-1 ring-sky-400/25 transition hover:bg-sky-500/25"
      >
        + portfolio
      </button>
    )
  }
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <input className={`${inputCls} w-16`} type="number" min="0" step="any" placeholder="qty"
             value={shares} onChange={(e) => setShares(e.target.value)} autoFocus />
      <input className={`${inputCls} w-20`} type="number" min="0" step="any" placeholder="cost"
             value={cost} onChange={(e) => setCost(e.target.value)} />
      <input className={`${inputCls} w-32`} type="date" value={date}
             onChange={(e) => setDate(e.target.value)} />
      <button
        disabled={!(Number(shares) > 0 && Number(cost) > 0 && date)}
        onClick={() => {
          addPosition({
            ticker: a.ticker, market: a.market, shares: Number(shares),
            avg_cost: Number(cost), date, added_from: a.rule,
          })
          setOpen(false)
        }}
        className="rounded-lg bg-emerald-500/20 px-2.5 py-1 text-xs font-medium text-emerald-300 ring-1 ring-emerald-400/30 disabled:opacity-40"
      >
        add
      </button>
      <button onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:text-slate-300">
        ×
      </button>
    </span>
  )
}

const CONSENSUS_LABELS: Record<string, { label: string; style: string }> = {
  strong_buy: { label: 'Strong buy', style: 'bg-emerald-500/20 text-emerald-300' },
  buy: { label: 'Buy', style: 'bg-emerald-500/15 text-emerald-400' },
  hold: { label: 'Hold', style: 'bg-amber-500/15 text-amber-400' },
  underperform: { label: 'Underperform', style: 'bg-rose-500/15 text-rose-400' },
  sell: { label: 'Sell', style: 'bg-rose-500/20 text-rose-300' },
}

function AnalystSection({ f }: { f: Fundamentals }) {
  const a = f.analyst
  if (!a) return null
  const { target_low: lo, target_mean: mid, target_high: hi, price } = a
  const hasRange = lo !== undefined && hi !== undefined && hi > lo
  const pos = (v: number) => Math.min(100, Math.max(0, ((v - lo!) / (hi! - lo!)) * 100))
  const consensus = a.consensus ? CONSENSUS_LABELS[a.consensus] : null
  const upside = mid && price ? (mid / price - 1) * 100 : null
  return (
    <div className="mt-3 rounded-xl bg-white/[0.03] p-3.5 ring-1 ring-white/5">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium text-slate-200">Analyst view</span>
        {consensus && (
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${consensus.style}`}>
            {consensus.label}
          </span>
        )}
        {a.n_analysts !== undefined && (
          <span className="text-xs text-slate-500">{a.n_analysts} analysts</span>
        )}
        {upside !== null && (
          <span className={`text-xs ${upside >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            mean target {upside >= 0 ? '+' : ''}
            {upside.toFixed(1)}% from here
          </span>
        )}
      </div>
      {hasRange && (
        <div className="px-1 pb-1 pt-3">
          <div className="relative h-1.5 rounded-full bg-slate-700/60">
            {mid !== undefined && (
              <div
                title={`Mean target ${mid.toFixed(2)}`}
                className="absolute top-1/2 h-3.5 w-0.5 -translate-y-1/2 bg-sky-400"
                style={{ left: `${pos(mid)}%` }}
              />
            )}
            {price !== undefined && (
              <div
                title={`Current price ${price.toFixed(2)}`}
                className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-slate-950 bg-slate-100"
                style={{ left: `${pos(price)}%` }}
              />
            )}
          </div>
          <div className="mt-1.5 flex justify-between text-xs text-slate-500">
            <span>low {lo!.toFixed(0)}</span>
            <span className="text-sky-400">mean {mid !== undefined ? mid.toFixed(0) : '—'}</span>
            <span>high {hi!.toFixed(0)}</span>
          </div>
        </div>
      )}
      {(f.rating_changes?.length ?? 0) > 0 && (
        <ul className="mt-2 space-y-1 border-t border-slate-800/70 pt-2 text-xs">
          {f.rating_changes!.map((c, i) => (
            <li key={i} className="flex flex-wrap gap-x-2 text-slate-400">
              <span className="text-slate-500">{c.date}</span>
              <span className="text-slate-300">{c.firm}</span>
              <span
                className={
                  c.action === 'up'
                    ? 'text-emerald-400'
                    : c.action === 'down'
                      ? 'text-rose-400'
                      : 'text-slate-400'
                }
              >
                {c.from_grade && c.from_grade !== c.to_grade
                  ? `${c.from_grade} → ${c.to_grade}`
                  : c.to_grade}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

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

// ---- Suggestion quality: presentational ranking of BUYs by confluence ----
// Purely a display score (the verdict itself is unchanged): how many
// independent lenses agree with this buy, weighted by what backtests showed
// matters. Formula documented in the page footer.
export function qualityScore(a: AlertItem): number {
  let s = 3 // base: passed all three verdict layers (it IS a buy)
  const rating = a.fundamentals?.rating
  if (rating === 'strong') s += 2
  else if (rating === 'neutral') s += 1
  const sec = a.sector?.state
  if (sec === 'leading') s += 1.5
  else if (sec === 'improving') s += 0.5
  else if (sec === 'weakening') s -= 0.25 // rotation out already underway
  else if (sec === 'lagging') s -= 0.5
  const vol = a.volume?.ratio
  // average volume is NOT confirmation — credit starts above it
  if (vol !== undefined) s += vol >= 2 ? 1.5 : vol >= 1.25 ? 1 : vol >= 1 ? 0.5 : 0
  // consensus adds only a small kicker: the fundamentals rating above already
  // contains analyst factors, so full weight here would double-count them
  const consensus = a.fundamentals?.analyst?.consensus
  if (consensus === 'strong_buy') s += 0.5
  else if (consensus === 'buy') s += 0.25
  if (a.rule === 'PRICE_SMA200W_BULL') s += 1 // secular cross: rarest, highest-quality signal
  else if (a.rule === 'GOLDEN_CROSS') s += 0.5
  const fibDist = a.fib?.daily?.nearest.dist_pct
  if (fibDist !== undefined && fibDist >= 0 && fibDist <= 3) s += 0.5 // sitting on support
  return Math.max(0, s)
}

// thresholds scaled to the achievable max of 10 (non-US names top out at 8.5
// since sector rotation is US-only — evidence-based, noted in the footer)
const GRADES: { min: number; label: string; style: string }[] = [
  { min: 7.5, label: 'Strong+', style: 'bg-emerald-500/25 text-emerald-200 ring-emerald-400/40' },
  { min: 6, label: 'Strong', style: 'bg-emerald-500/15 text-emerald-300 ring-emerald-400/25' },
  { min: 5, label: 'Good', style: 'bg-sky-500/15 text-sky-300 ring-sky-400/25' },
  { min: 0, label: 'Fair', style: 'bg-slate-500/15 text-slate-300 ring-white/10' },
]

export function gradeOf(score: number) {
  return GRADES.find((g) => score >= g.min) ?? GRADES[GRADES.length - 1]
}

function QualityBadge({ score }: { score: number }) {
  const g = gradeOf(score)
  return (
    <span
      title={`Quality score ${score.toFixed(1)} — confluence across fundamentals, sector, volume, analysts, signal rarity, Fib support`}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${g.style}`}
    >
      {g.label}
      <span className="tnum font-normal opacity-70">{score.toFixed(1)}</span>
    </span>
  )
}

function BuyCard({ a, rank, defaultOpen }: { a: AlertItem; rank: number; defaultOpen: boolean }) {
  const f = a.fundamentals
  const [open, setOpen] = useState(defaultOpen)
  const pct = a.values.sma200 ? ((a.close - a.values.sma200) / a.values.sma200) * 100 : null
  const score = qualityScore(a)
  return (
    <div className="rounded-2xl bg-gradient-to-b from-slate-900/60 to-slate-900/20 ring-1 ring-white/5 transition hover:ring-sky-400/20">
      <div
        role="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex cursor-pointer flex-wrap items-center justify-between gap-x-3 gap-y-2 px-5 py-3.5 select-none"
      >
        <div className="flex flex-wrap items-center gap-2.5">
          <span className={`text-slate-500 transition-transform ${open ? 'rotate-90' : ''}`}>▸</span>
          <span className="w-6 text-right text-sm text-slate-600">{rank}</span>
          <a
            href={tradingViewUrl(a.ticker)}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-base font-bold text-sky-400 hover:text-sky-300 hover:underline"
          >
            {a.ticker} ↗
          </a>
          <MarketBadge market={a.market} />
          <QualityBadge score={score} />
          <span className="hidden text-xs text-slate-500 sm:inline">
            {CATEGORY_LABELS[a.category] ?? a.category}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="tnum text-sm text-slate-300">
            {a.close >= 10 ? a.close.toFixed(2) : a.close.toFixed(4)}
            {pct !== null && (
              <span className={`ml-2 ${pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {pct >= 0 ? '+' : ''}
                {pct.toFixed(2)}%
              </span>
            )}
          </span>
          <span onClick={(e) => e.stopPropagation()}>
            <AddToPortfolio a={a} />
          </span>
        </div>
      </div>

      {open && (
        <div className="border-t border-white/5 px-5 pb-5 pt-3">
          <p className="text-sm text-slate-400">
            {a.verdict_reason} · <span className="text-emerald-400">MACD confirms</span>
            <span className="ml-2 text-slate-500">{a.date}</span>
          </p>

          {f ? (
        <div className="mt-3 rounded-xl bg-white/[0.03] p-3.5 ring-1 ring-white/5">
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
          {a.sector && (
            <div className="mt-2 flex items-center justify-between border-t border-white/5 pt-2 text-sm">
              <span className="text-slate-400">
                Sector — <span className="text-slate-300">{a.sector.name}</span>
              </span>
              <span className="flex items-center gap-2">
                {a.sector.state ? (
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${
                      SECTOR_STATE[a.sector.state].style
                    }`}
                  >
                    {SECTOR_STATE[a.sector.state].label}
                  </span>
                ) : (
                  <span className="text-xs text-slate-500">no data</span>
                )}
                <span className="w-12 text-right">
                  <FactorChip value={a.sector.factor} />
                </span>
              </span>
            </div>
          )}
          <AnalystSection f={f} />
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          Fundamentals unavailable for this ticker — verdict is technicals + MACD only.
        </p>
      )}
          <PriceStructure a={a} />
        </div>
      )}
    </div>
  )
}

function FibLadder({ frame, label }: { frame: FibFrame; label: string }) {
  const { high, low, position_pct, levels, nearest } = frame
  const clampedPos = Math.max(0, Math.min(100, position_pct))
  return (
    <div className="mt-2">
      <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
        <span className="font-medium text-slate-300">{label}</span>
        <span>
          swing {low.toFixed(2)}–{high.toFixed(2)} · at{' '}
          <span className="text-slate-200">{position_pct.toFixed(0)}%</span> of range
        </span>
      </div>
      {/* position within the swing range, with the current price marker */}
      <div className="relative h-1.5 rounded-full bg-slate-700/50">
        <div
          className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-slate-950 bg-slate-100"
          style={{ left: `${clampedPos}%` }}
          title={`Price at ${position_pct.toFixed(1)}% of the ${low.toFixed(2)}–${high.toFixed(2)} range`}
        />
      </div>
      <div className="mt-2 grid grid-cols-5 gap-1 text-center text-xs">
        {levels.map((l) => {
          const isNear = l.label === nearest.label
          return (
            <div
              key={l.label}
              className={`rounded-md px-1 py-1 ${
                isNear ? 'bg-sky-500/15 ring-1 ring-sky-400/25' : 'bg-white/[0.02]'
              }`}
            >
              <div className="text-slate-400">{l.label}</div>
              <div className="text-slate-200">{l.price.toFixed(2)}</div>
              <div className={l.dist_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                {l.dist_pct >= 0 ? '+' : ''}
                {l.dist_pct.toFixed(1)}%
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PriceStructure({ a }: { a: AlertItem }) {
  const daily = a.fib?.daily
  const weekly = a.fib?.weekly
  const vol = a.volume
  if (!daily && !weekly && !vol) return null
  return (
    <div className="mt-3 rounded-xl bg-white/[0.03] p-3.5 ring-1 ring-white/5">
      <div className="mb-1 flex items-center gap-2 text-sm">
        <span className="font-medium text-slate-200">Price structure</span>
        <span className="text-xs text-slate-500">Fibonacci retracements · nearest level highlighted</span>
      </div>
      {daily && <FibLadder frame={daily} label="Daily (1-year swing)" />}
      {weekly && <FibLadder frame={weekly} label="Weekly (2-year swing)" />}
      {vol && (
        <div className="mt-3 flex items-center justify-between border-t border-white/5 pt-2 text-sm">
          <span className="text-slate-400">Volume vs 20-day average</span>
          <span className={vol.above_avg ? 'text-emerald-400' : 'text-slate-300'}>
            {vol.ratio.toFixed(2)}× {vol.above_avg ? '(above)' : '(below)'}
          </span>
        </div>
      )}
    </div>
  )
}

export default function BuysPage() {
  const { latest, error } = useAlerts()

  if (error) {
    return (
      <p className="rounded-xl border border-dashed border-white/10 bg-white/[0.01] px-4 py-8 text-center text-sm text-slate-500">
        No scan data yet.
      </p>
    )
  }
  if (!latest) return <p className="py-8 text-center text-slate-500">Loading…</p>

  const buys = latest.alerts
    .filter((a) => a.verdict === 'buy')
    .map((a) => ({ a, score: qualityScore(a) }))
    .sort((x, y) => y.score - x.score)

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight text-slate-100"><span className="h-4 w-1 rounded-full bg-sky-400/70" />
          BUY verdicts — {latest.bar_date} · ranked by quality
        </h2>
        <span className="text-sm text-slate-500">
          {buys.length} of {latest.alerts.length} alerts passed all three layers
        </span>
      </div>

      {buys.length > 0 ? (
        <div className="space-y-2.5">
          {buys.map(({ a }, i) => (
            <BuyCard key={`${a.rule}-${a.ticker}`} a={a} rank={i + 1} defaultOpen={false} />
          ))}
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-white/10 bg-white/[0.01] px-4 py-8 text-center text-sm text-slate-500">
          No BUY verdicts on {latest.bar_date} — signal, MACD, and fundamentals did not align on any name.
        </p>
      )}

      <p className="text-xs text-slate-500">
        A BUY requires all three layers to agree: a bullish signal, MACD momentum
        confirmation, and fundamentals that are not weak. Click a row to expand its
        full detail. <span className="text-slate-400">Quality</span> is a display-only
        confluence score (it does not change the verdict): base 3 for any BUY, plus
        fundamentals (strong +2 / neutral +1), sector (leading +1.5 / improving +0.5 /
        weakening −0.25 / lagging −0.5; US-only, so non-US names top out lower),
        volume (≥2× avg +1.5 / ≥1.25× +1 / ≥1× +0.5), a small analyst kicker
        (strong buy +0.5 / buy +0.25 — the fundamentals rating already counts analyst
        factors), signal rarity (200-week cross +1 / golden cross +0.5), and price
        sitting on Fib support (+0.5). Strong+ ≥7.5 · Strong ≥6 · Good ≥5 · Fair
        below. Informational, not investment advice.
      </p>
    </section>
  )
}
