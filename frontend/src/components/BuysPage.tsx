import { useState } from 'react'
import { useAlerts, usePortfolio } from '../hooks/useAlerts'
import { addPosition } from '../lib/portfolio'
import { tradingViewUrl } from '../lib/tradingview'
import { badgeFlat, badgeRing, inputClsSm, type Tone } from '../lib/ui'
import type { AlertItem, FibFrame, Fundamentals } from '../types'
import { CATEGORY_LABELS, CATEGORY_SHORT, CONSENSUS_LABELS, SECTOR_STATE } from '../types'
import { MarketBadge } from './AlertTable'
import Badge from './ui/Badge'
import SectionHeading from './ui/SectionHeading'

function AddToPortfolio({ a }: { a: AlertItem }) {
  const { positions } = usePortfolio()
  const [open, setOpen] = useState(false)
  const [shares, setShares] = useState('')
  const [cost, setCost] = useState(String(a.close))
  const [date, setDate] = useState(a.date)
  const held = positions.some((p) => p.ticker === a.ticker)

  if (held && !open) {
    return (
      <span className={`rounded px-2.5 py-1 text-xs font-medium ${badgeRing.up}`}>
        ✓ in portfolio
      </span>
    )
  }
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className={`rounded px-2.5 py-1 text-xs font-medium transition ${badgeRing.accent} hover:bg-accent/20`}
      >
        + portfolio
      </button>
    )
  }
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <input className={`${inputClsSm} w-16`} type="number" min="0" step="any" placeholder="qty"
             value={shares} onChange={(e) => setShares(e.target.value)} autoFocus />
      <input className={`${inputClsSm} w-20`} type="number" min="0" step="any" placeholder="cost"
             value={cost} onChange={(e) => setCost(e.target.value)} />
      <input className={`${inputClsSm} w-32`} type="date" value={date}
             onChange={(e) => setDate(e.target.value)} />
      <button
        disabled={!(Number(shares) > 0 && Number(cost) > 0 && date)}
        onClick={() => {
          const target = a.fundamentals?.analyst?.target_mean
          addPosition({
            ticker: a.ticker, market: a.market, shares: Number(shares),
            avg_cost: Number(cost), date, added_from: a.rule,
            ...(target ? { target_mean: target, target_as_of: a.date } : {}),
          })
          setOpen(false)
        }}
        className={`rounded px-2.5 py-1 text-xs font-medium disabled:opacity-40 ${badgeRing.up} hover:bg-up/20`}
      >
        add
      </button>
      <button onClick={() => setOpen(false)} className="text-xs text-muted hover:text-ink">
        ×
      </button>
    </span>
  )
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
    <div className="mt-3 bg-raised p-3.5 ring-1 ring-hair">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium text-ink">Analyst view</span>
        {consensus && (
          <span className={`rounded px-2.5 py-0.5 text-xs font-semibold ${badgeFlat[consensus.tone]}`}>
            {consensus.label}
          </span>
        )}
        {a.n_analysts !== undefined && (
          <span className="text-xs text-muted">{a.n_analysts} analysts</span>
        )}
        {upside !== null && (
          <span className={`text-xs ${upside >= 0 ? 'text-up' : 'text-down'}`}>
            mean target {upside >= 0 ? '+' : ''}
            {upside.toFixed(1)}% from here
          </span>
        )}
      </div>
      {hasRange && (
        <div className="px-1 pb-1 pt-3">
          <div className="relative h-1.5 bg-overlay">
            {mid !== undefined && (
              <div
                title={`Mean target ${mid.toFixed(2)}`}
                className="absolute top-1/2 h-3.5 w-0.5 -translate-y-1/2 bg-accent"
                style={{ left: `${pos(mid)}%` }}
              />
            )}
            {price !== undefined && (
              <div
                title={`Current price ${price.toFixed(2)}`}
                className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 border-2 border-base bg-ink"
                style={{ left: `${pos(price)}%` }}
              />
            )}
          </div>
          <div className="mt-1.5 flex justify-between text-xs text-muted">
            <span>low {lo!.toFixed(0)}</span>
            <span className="text-accent">mean {mid !== undefined ? mid.toFixed(0) : '—'}</span>
            <span>high {hi!.toFixed(0)}</span>
          </div>
        </div>
      )}
      {(f.rating_changes?.length ?? 0) > 0 && (
        <ul className="mt-2 space-y-1 border-t border-hair pt-2 text-xs">
          {f.rating_changes!.map((c, i) => (
            <li key={i} className="flex flex-wrap gap-x-2 text-ink-2">
              <span className="text-muted">{c.date}</span>
              <span className="text-ink">{c.firm}</span>
              <span
                className={
                  c.action === 'up' ? 'text-up' : c.action === 'down' ? 'text-down' : 'text-muted'
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
    return <span className="rounded bg-overlay px-2 py-0.5 text-xs text-muted">n/a</span>
  const tone: Tone = value > 0 ? 'up' : value < 0 ? 'down' : 'neutral'
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${badgeFlat[tone]}`}>
      {value > 0 ? '+1' : value < 0 ? '−1' : '0'}
    </span>
  )
}

// ---- Company profile: display-only fundamentals context (not scored) ----
const pct1 = (v: number) => `${v.toFixed(1)}%`
const signed1 = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
const mult1 = (v: number) => `${v.toFixed(1)}×`
const mult2 = (v: number) => `${v.toFixed(2)}×`

const PROFILE_ROWS: { key: string; label: string; fmt: (v: number) => string }[] = [
  { key: 'roe', label: 'Return on equity', fmt: pct1 },
  { key: 'gross_margin', label: 'Gross margin', fmt: pct1 },
  { key: 'op_margin', label: 'Operating margin', fmt: pct1 },
  { key: 'net_margin', label: 'Net margin', fmt: pct1 },
  { key: 'rev_growth', label: 'Revenue growth', fmt: signed1 },
  { key: 'net_debt_to_ebitda', label: 'Net debt / EBITDA', fmt: mult1 },
  { key: 'debt_to_equity', label: 'Debt / equity', fmt: mult1 },
  { key: 'current_ratio', label: 'Current ratio', fmt: mult2 },
  { key: 'ev_ebitda', label: 'EV / EBITDA', fmt: mult1 },
  { key: 'peg', label: 'PEG', fmt: mult2 },
  { key: 'p_fcf', label: 'Price / FCF', fmt: mult1 },
  { key: 'div_yield', label: 'Dividend yield', fmt: pct1 },
  { key: 'payout', label: 'Payout ratio', fmt: pct1 },
]

const FLAG_LABELS: Record<string, string> = {
  high_leverage: '⚠ High leverage',
  value_trap: '⚠ Possible value trap',
  earnings_not_cash_backed: '⚠ Earnings not cash-backed',
}

function ProfileTable({ profile }: { profile: Record<string, number> }) {
  const rows = PROFILE_ROWS.filter((r) => profile[r.key] !== undefined)
  if (rows.length === 0) return null
  return (
    <div className="mt-2 border-t border-hair pt-2">
      <div className="mb-1 text-xs text-muted">
        Company profile <span className="text-faint">· context, not part of the score</span>
      </div>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td className="py-1 text-muted">{r.label}</td>
              <td className="tnum py-1 text-right text-ink">{r.fmt(profile[r.key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
const GRADES: { min: number; label: string; tone: Tone }[] = [
  { min: 7.5, label: 'Strong+', tone: 'up' },
  { min: 6, label: 'Strong', tone: 'up' },
  { min: 5, label: 'Good', tone: 'info' },
  { min: 0, label: 'Fair', tone: 'neutral' },
]

export function gradeOf(score: number) {
  return GRADES.find((g) => score >= g.min) ?? GRADES[GRADES.length - 1]
}

function QualityBadge({ score }: { score: number }) {
  const g = gradeOf(score)
  return (
    <span
      title={`Quality score ${score.toFixed(1)} — confluence across fundamentals, sector, volume, analysts, signal rarity, Fib support`}
      className={`inline-flex items-center gap-1.5 rounded px-2.5 py-0.5 text-xs font-semibold ${badgeRing[g.tone]}`}
    >
      {g.label}
      <span className="tnum font-normal opacity-70">{score.toFixed(1)}</span>
    </span>
  )
}

// How fresh is this signal? Compared against the latest bar for its OWN market
// (markets have different holidays/close times), so a daily cross that fired on
// the latest bar reads NEW while a 200-week cross — which only ever carries the
// prior completed Friday — correctly reads a few days old.
function FreshnessChip({ date, refDate }: { date: string; refDate: string }) {
  const days = Math.round((Date.parse(refDate) - Date.parse(date)) / 86400000)
  const fresh = days <= 0
  const label = fresh ? 'NEW' : days === 1 ? '1d old' : `${days}d old`
  return (
    <span
      title={
        fresh
          ? `Signal fired ${date} — the latest bar for this market, so it is today's cross`
          : `Signal fired ${date} · ${days} day${days === 1 ? '' : 's'} before this market's latest bar (${refDate})`
      }
      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold ${
        fresh ? badgeRing.up : badgeRing.neutral
      }`}
    >
      {label}
      <span className="tnum font-normal opacity-70">{date}</span>
    </span>
  )
}

function BuyCard({ a, rank, defaultOpen, refDate, refire = false }: {
  a: AlertItem; rank: number; defaultOpen: boolean; refDate: string; refire?: boolean
}) {
  const f = a.fundamentals
  const [open, setOpen] = useState(defaultOpen)
  const pct = a.values.sma200 ? ((a.close - a.values.sma200) / a.values.sma200) * 100 : null
  const score = qualityScore(a)
  return (
    <div className="bg-raised ring-1 ring-hair transition hover:ring-accent/30">
      <div
        role="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex cursor-pointer flex-wrap items-center justify-between gap-x-3 gap-y-2 px-5 py-3 select-none"
      >
        <div className="flex flex-wrap items-center gap-2.5">
          <span className={`text-muted transition-transform ${open ? 'rotate-90' : ''}`}>▸</span>
          <span className="w-6 text-right text-sm text-faint">{rank}</span>
          <a
            href={tradingViewUrl(a.ticker)}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-base font-bold text-info hover:underline"
          >
            {a.ticker} ↗
          </a>
          <MarketBadge market={a.market} />
          <QualityBadge score={score} />
          <FreshnessChip date={a.date} refDate={refDate} />
          {refire && (
            <span className="text-[10px] text-muted"
                  title="Same signal fired within the last 14 days — possible whipsaw around the SMA">
              ↩ re-entry
            </span>
          )}
          <span className="hidden text-xs text-muted sm:inline"
                title={CATEGORY_LABELS[a.category] ?? a.category}>
            {CATEGORY_SHORT[a.category] ?? a.category}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="tnum text-sm text-ink-2">
            {a.close >= 10 ? a.close.toFixed(2) : a.close.toFixed(4)}
            {pct !== null && (
              <span className={`ml-2 ${pct >= 0 ? 'text-up' : 'text-down'}`}>
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
        <div className="border-t border-hair px-5 pb-5 pt-3">
          <p className="text-sm text-muted">
            {a.verdict_reason} · <span className="text-up">MACD confirms</span>
            <span className="ml-2 text-faint">{a.date}</span>
          </p>

          {f ? (
        <div className="mt-3 bg-raised p-3.5 ring-1 ring-hair">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium text-ink">Fundamentals</span>
            <span
              className={`rounded px-2.5 py-0.5 text-xs font-semibold uppercase ${
                f.rating === 'strong'
                  ? badgeFlat.up
                  : f.rating === 'weak'
                    ? badgeFlat.down
                    : badgeFlat.neutral
              }`}
            >
              {f.rating} ({f.score >= 0 ? '+' : ''}
              {f.score})
            </span>
            {f.coverage && (
              <span
                className="text-xs text-muted"
                title="How many of the 5 scored factors had data — fewer means a thinner read. Separate from the company-profile metrics below."
              >
                {f.coverage.present}/{f.coverage.total} factors
              </span>
            )}
            {f.flags?.map((flag) => (
              <span key={flag} className={`rounded px-2 py-0.5 text-xs font-semibold ${badgeRing.down}`}>
                {FLAG_LABELS[flag] ?? flag}
              </span>
            ))}
          </div>
          {f.summary && <p className="mb-2 text-sm text-ink-2">{f.summary}</p>}
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(FACTOR_LABELS).map(([key, def]) => (
                <tr key={key}>
                  <td className="py-1 text-muted">{def.label}</td>
                  <td className="tnum py-1 text-right text-ink">{def.fmt(f.metrics ?? {})}</td>
                  <td className="w-12 py-1 text-right">
                    <FactorChip value={f.factors?.[key]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {f.profile && <ProfileTable profile={f.profile} />}
          {a.sector && (
            <div className="mt-2 flex items-center justify-between border-t border-hair pt-2 text-sm">
              <span className="text-muted">
                Sector — <span className="text-ink-2">{a.sector.name}</span>
              </span>
              <span className="flex items-center gap-2">
                {a.sector.state ? (
                  <Badge tone={SECTOR_STATE[a.sector.state].tone}>
                    {SECTOR_STATE[a.sector.state].label}
                  </Badge>
                ) : (
                  <span className="text-xs text-muted">no data</span>
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
        <p className="mt-3 text-sm text-muted">
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
      <div className="mb-1 flex items-center justify-between text-xs text-muted">
        <span className="font-medium text-ink-2">{label}</span>
        <span>
          swing {low.toFixed(2)}–{high.toFixed(2)} · at{' '}
          <span className="text-ink">{position_pct.toFixed(0)}%</span> of range
        </span>
      </div>
      {/* position within the swing range, with the current price marker */}
      <div className="relative h-1.5 bg-overlay">
        <div
          className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 border-2 border-base bg-ink"
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
              className={`rounded px-1 py-1 ${
                isNear ? 'bg-accent/15 ring-1 ring-accent/30' : 'bg-overlay'
              }`}
            >
              <div className="text-muted">{l.label}</div>
              <div className="tnum text-ink">{l.price.toFixed(2)}</div>
              <div className={`tnum ${l.dist_pct >= 0 ? 'text-up' : 'text-down'}`}>
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
    <div className="mt-3 bg-raised p-3.5 ring-1 ring-hair">
      <div className="mb-1 flex items-center gap-2 text-sm">
        <span className="font-medium text-ink">Price structure</span>
        <span className="text-xs text-muted">Fibonacci retracements · nearest level highlighted</span>
      </div>
      {daily && <FibLadder frame={daily} label="Daily (1-year swing)" />}
      {weekly && <FibLadder frame={weekly} label="Weekly (2-year swing)" />}
      {vol && (
        <div className="mt-3 flex items-center justify-between border-t border-hair pt-2 text-sm">
          <span className="text-muted">Volume vs 20-day average</span>
          <span className={`tnum ${vol.above_avg ? 'text-up' : 'text-ink-2'}`}>
            {vol.ratio.toFixed(2)}× {vol.above_avg ? '(above)' : '(below)'}
          </span>
        </div>
      )}
    </div>
  )
}

type SortMode = 'quality' | 'newest'

export default function BuysPage() {
  const { latest, history, error } = useAlerts()
  const { positions } = usePortfolio()
  const [showHeld, setShowHeld] = useState(false)
  const [sort, setSort] = useState<SortMode>('quality')
  const [showRecent, setShowRecent] = useState(false)
  const [openDays, setOpenDays] = useState<Set<string>>(new Set())
  const toggleDay = (d: string) =>
    setOpenDays((prev) => {
      const next = new Set(prev)
      next.has(d) ? next.delete(d) : next.add(d)
      return next
    })

  // same ticker+rule alerted within the prior 14 days → tag as re-entry
  const isRefire = (a: AlertItem): boolean => {
    if (!history) return false
    const t = new Date(a.date).getTime()
    return history.days.some((d) =>
      d.alerts.some((o) =>
        o.ticker === a.ticker && o.rule === a.rule && o.date < a.date &&
        t - new Date(o.date).getTime() <= 14 * 86400000))
  }

  if (error) {
    return (
      <p className="border border-dashed border-hair bg-raised px-4 py-8 text-center text-sm text-muted">
        No scan data yet.
      </p>
    )
  }
  if (!latest) return <p className="py-8 text-center text-muted">Loading…</p>

  // reference "latest bar" per market — a stale market keeps its own last bar,
  // so freshness is judged against the right calendar, not the global one
  const refDateFor = (a: AlertItem) => latest.bar_dates?.[a.market ?? 'us'] ?? latest.bar_date
  // days between the signal and its market's latest bar (0 = NEW), matching the
  // freshness chip; "newest" sorts by this, quality breaking ties
  const ageDays = (a: AlertItem) =>
    Math.round((Date.parse(refDateFor(a)) - Date.parse(a.date)) / 86400000)

  const held = new Set(positions.map((p) => p.ticker))
  const all = latest.alerts
    .filter((a) => a.verdict === 'buy')
    .map((a) => ({ a, score: qualityScore(a) }))
    .sort((x, y) =>
      sort === 'newest'
        ? ageDays(x.a) - ageDays(y.a) || y.score - x.score
        : y.score - x.score,
    )
  // stocks you already own aren't fresh opportunities — group them separately
  const buys = all.filter(({ a }) => !held.has(a.ticker))
  const heldBuys = all.filter(({ a }) => held.has(a.ticker))

  // the previous 5 scan days' BUY verdicts (today is the main list above),
  // each day quality-ranked — history.days is newest-first
  const recentDays = (history?.days ?? [])
    .filter((d) => d.bar_date !== latest.bar_date)
    .slice(0, 5)
    .map((d) => ({
      date: d.bar_date,
      buys: d.alerts
        .filter((a) => a.verdict === 'buy')
        .map((a) => ({ a, score: qualityScore(a) }))
        .sort((x, y) => y.score - x.score),
    }))
    .filter((d) => d.buys.length > 0)

  return (
    <section className="space-y-4">
      <SectionHeading
        title={`BUY verdicts — ${latest.bar_date} · ${sort === 'newest' ? 'newest first' : 'ranked by quality'}`}
        right={
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <div className="flex items-center gap-1 text-xs">
              <span className="text-muted">Sort</span>
              {(['quality', 'newest'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setSort(m)}
                  className={`rounded px-2 py-0.5 font-medium transition ${
                    sort === m ? badgeRing.accent : 'text-muted hover:text-ink'
                  }`}
                >
                  {m === 'quality' ? 'Quality' : 'Newest'}
                </button>
              ))}
            </div>
            <span className="text-sm text-muted">
              {all.length} of {latest.alerts.length} alerts passed all three layers
            </span>
          </div>
        }
      />

      {buys.length > 0 ? (
        <div className="space-y-2.5">
          {buys.map(({ a }, i) => (
            <BuyCard key={`${a.rule}-${a.ticker}`} a={a} rank={i + 1} defaultOpen={false}
                     refDate={refDateFor(a)} refire={isRefire(a)} />
          ))}
        </div>
      ) : (
        <p className="border border-dashed border-hair bg-raised px-4 py-8 text-center text-sm text-muted">
          {all.length > 0
            ? `All ${all.length} BUY verdicts on ${latest.bar_date} are stocks you already hold (below).`
            : `No BUY verdicts on ${latest.bar_date} — signal, MACD, and fundamentals did not align on any name.`}
        </p>
      )}

      {heldBuys.length > 0 && (
        <div className="space-y-2.5">
          <button
            onClick={() => setShowHeld(!showHeld)}
            className="flex items-center gap-2 text-sm text-muted transition-colors hover:text-ink"
          >
            <span className={`transition-transform ${showHeld ? 'rotate-90' : ''}`}>▸</span>
            Already held ({heldBuys.length}) — re-confirming signals on stocks in your portfolio
          </button>
          {showHeld &&
            heldBuys.map(({ a }, i) => (
              <BuyCard key={`held-${a.rule}-${a.ticker}`} a={a} rank={buys.length + i + 1}
                       defaultOpen={false} refDate={refDateFor(a)} refire={isRefire(a)} />
            ))}
        </div>
      )}

      {recentDays.length > 0 && (
        <div className="space-y-2.5 border-t border-hair pt-4">
          <button
            onClick={() => setShowRecent(!showRecent)}
            className="flex items-center gap-2 text-sm text-muted transition-colors hover:text-ink"
          >
            <span className={`transition-transform ${showRecent ? 'rotate-90' : ''}`}>▸</span>
            Earlier BUY verdicts — last {recentDays.length} scan day
            {recentDays.length > 1 ? 's' : ''} ({recentDays.reduce((n, d) => n + d.buys.length, 0)})
          </button>
          {showRecent && (
            <div className="space-y-2.5 border-l border-hair pl-3">
              {recentDays.map(({ date, buys: dayBuys }) => {
                const dayOpen = openDays.has(date)
                return (
                  <div key={date} className="space-y-2.5">
                    <button
                      onClick={() => toggleDay(date)}
                      className="flex items-center gap-2 text-sm text-ink-2 transition-colors hover:text-ink"
                    >
                      <span className={`transition-transform ${dayOpen ? 'rotate-90' : ''}`}>▸</span>
                      <span className="tnum">{date}</span>
                      <span className="text-muted">
                        — {dayBuys.length} BUY{dayBuys.length > 1 ? 's' : ''}
                      </span>
                    </button>
                    {dayOpen &&
                      dayBuys.map(({ a }, i) => (
                        <BuyCard key={`${date}-${a.rule}-${a.ticker}`} a={a} rank={i + 1}
                                 defaultOpen={false} refDate={date} refire={isRefire(a)} />
                      ))}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-muted">
        A BUY requires all three layers to agree: a bullish signal, MACD momentum
        confirmation, and fundamentals that are not weak. Click a row to expand its
        full detail. <span className="text-ink-2">Quality</span> is a display-only
        confluence score (it does not change the verdict): base 3 for any BUY, plus
        fundamentals (strong +2 / neutral +1), sector (leading +1.5 / improving +0.5 /
        weakening −0.25 / lagging −0.5; US-only, so non-US names top out lower),
        volume (≥2× avg +1.5 / ≥1.25× +1 / ≥1× +0.5), a small analyst kicker
        (strong buy +0.5 / buy +0.25 — the fundamentals rating already counts analyst
        factors), signal rarity (200-week cross +1 / golden cross +0.5), and price
        sitting on Fib support (+0.5). Strong+ ≥7.5 · Strong ≥6 · Good ≥5 · Fair
        below. The <span className="text-up">NEW</span> / <span className="text-ink-2">Nd
        old</span> chip shows when each signal actually crossed relative to its market's
        latest bar — daily crosses read NEW, while a 200-week cross carries the prior
        completed Friday and so reads a few days old even when freshly listed.
        Informational, not investment advice.
      </p>
    </section>
  )
}
