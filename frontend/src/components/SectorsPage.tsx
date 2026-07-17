import { Fragment, useState } from 'react'
import { useSectors } from '../hooks/useAlerts'
import { tradingViewUrl } from '../lib/tradingview'
import { badgeFlat, tableWrapCls, theadCls, type Tone } from '../lib/ui'
import {
  CONSENSUS_LABELS,
  SECTOR_HORIZONS,
  SECTOR_STATE,
  type SectorConstituent,
  type SectorRow,
} from '../types'
import Badge from './ui/Badge'
import SectionHeading from './ui/SectionHeading'

// Color a return/RS cell: green scales up, red scales down, capped at ±8%.
// Colors read from the up/down tokens so the heatmap themes in light + dark.
function HeatCell({ v, suffix = '%' }: { v: number | null; suffix?: string }) {
  if (v === null || v === undefined)
    return <td className="px-3 py-2 text-right text-faint">—</td>
  const t = Math.min(1, Math.abs(v) / 8)
  const alpha = 0.06 + t * 0.2
  const bg = v >= 0 ? `rgb(var(--up) / ${alpha})` : `rgb(var(--down) / ${alpha})`
  return (
    <td className="px-3 py-2 text-right" style={{ backgroundColor: bg }}>
      <span className={v >= 0 ? 'text-up' : 'text-down'}>
        {v >= 0 ? '+' : ''}
        {v.toFixed(1)}
        {suffix}
      </span>
    </td>
  )
}

function StateBadge({ state }: { state: SectorRow['state'] }) {
  const s = SECTOR_STATE[state]
  return <Badge tone={s.tone}>{s.label}</Badge>
}

function fmtCap(v: number): string {
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`
  if (v >= 1e9) return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

// Small signed-percent text (no heat background — the sub-table stays quiet)
function Pct({ v, dash = '—' }: { v: number | null | undefined; dash?: string }) {
  if (v === null || v === undefined) return <span className="text-faint">{dash}</span>
  return (
    <span className={v >= 0 ? 'text-up' : 'text-down'}>
      {v >= 0 ? '+' : ''}
      {v.toFixed(1)}%
    </span>
  )
}

const RATING_TONES: Record<string, Tone> = { strong: 'up', neutral: 'neutral', weak: 'down' }

// The 10 biggest companies of an expanded sector, with compact fundamentals.
function ConstituentsTable({ rows }: { rows: SectorConstituent[] }) {
  return (
    <div className="overflow-x-auto bg-raised ring-1 ring-hair">
      <table className="w-full text-left text-xs">
        <thead className={theadCls}>
          <tr>
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">Company</th>
            <th className="px-3 py-2 text-right">Mkt cap</th>
            <th className="px-3 py-2 text-right">Price</th>
            <th className="px-3 py-2 text-right">1d</th>
            <th className="px-3 py-2 text-right">Fwd P/E</th>
            <th className="px-3 py-2 text-right">Div yld</th>
            <th className="px-3 py-2 text-right">Rev growth</th>
            <th className="px-3 py-2 text-right">Margin</th>
            <th className="px-3 py-2">Analysts</th>
            <th className="px-3 py-2 text-right">Target Δ</th>
            <th className="px-3 py-2 text-right">Fundamentals</th>
          </tr>
        </thead>
        <tbody className="tnum divide-y divide-hair">
          {rows.map((c, i) => {
            const f = c.fundamentals
            const consensus = f?.consensus ? CONSENSUS_LABELS[f.consensus] : null
            return (
              <tr key={c.ticker} className="text-ink-2">
                <td className="px-3 py-2 text-faint">{i + 1}</td>
                <td className="px-3 py-2">
                  <a
                    href={tradingViewUrl(c.ticker)}
                    target="_blank"
                    rel="noreferrer"
                    className="font-semibold text-info hover:underline"
                  >
                    {c.ticker}
                  </a>
                  <span className="ml-1.5 text-muted">{c.name}</span>
                </td>
                <td className="px-3 py-2 text-right text-ink">{fmtCap(c.cap)}</td>
                <td className="px-3 py-2 text-right">{c.price.toFixed(2)}</td>
                <td className="px-3 py-2 text-right"><Pct v={c.chg_1d_pct} /></td>
                <td className="px-3 py-2 text-right">
                  {f?.forward_pe !== undefined ? `${f.forward_pe.toFixed(1)}×` : '—'}
                </td>
                <td className="px-3 py-2 text-right">
                  {f?.div_yield_pct !== undefined ? `${f.div_yield_pct.toFixed(2)}%` : '—'}
                </td>
                <td className="px-3 py-2 text-right"><Pct v={f?.rev_growth_pct} /></td>
                <td className="px-3 py-2 text-right">
                  {f?.margin_pct !== undefined ? `${f.margin_pct.toFixed(1)}%` : '—'}
                </td>
                <td className="px-3 py-2">
                  {consensus ? (
                    <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ${badgeFlat[consensus.tone]}`}>
                      {consensus.label}
                    </span>
                  ) : (
                    <span className="text-faint">—</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right"><Pct v={f?.target_upside_pct} /></td>
                <td className="px-3 py-2 text-right">
                  {f ? (
                    <span className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${badgeFlat[RATING_TONES[f.rating] ?? 'neutral']}`}>
                      {f.rating} {f.score >= 0 ? '+' : ''}{f.score}
                    </span>
                  ) : (
                    <span className="text-faint">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function SectorLeaderRow({ s }: { s: SectorRow }) {
  const [open, setOpen] = useState(false)
  const expandable = (s.top?.length ?? 0) > 0
  return (
    <Fragment>
      <tr
        onClick={() => expandable && setOpen(!open)}
        title={s.comment}
        aria-expanded={expandable ? open : undefined}
        className={`transition-colors hover:bg-overlay ${expandable ? 'cursor-pointer select-none' : ''}`}
      >
        <td className="px-3 py-2 text-muted">{s.rank}</td>
        <td className="px-3 py-2">
          {expandable && (
            <span className={`mr-1.5 inline-block text-muted transition-transform ${open ? 'rotate-90' : ''}`}>
              ▸
            </span>
          )}
          <a
            href={tradingViewUrl(s.symbol)}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="font-medium text-ink hover:text-info hover:underline"
          >
            {s.name}
          </a>
          <span className="ml-1.5 text-xs text-muted">{s.symbol}</span>
        </td>
        <td className="px-3 py-2"><StateBadge state={s.state} /></td>
        <HeatCell v={s.rs['1m']} suffix="" />
        <HeatCell v={s.rs['3m']} suffix="" />
        <td className="px-3 py-2">
          <span className={s.above_sma200 ? 'text-up' : 'text-down'}>
            {s.above_sma200 ? '▲' : '▼'} SMA200
          </span>
        </td>
        {SECTOR_HORIZONS.map((h) => (
          <HeatCell key={h} v={s.chg[h]} />
        ))}
      </tr>
      {open && expandable && (
        <tr>
          <td colSpan={6 + SECTOR_HORIZONS.length} className="bg-inset px-3 pb-3 pt-2 sm:px-4">
            <div className="mb-1.5 text-xs text-muted">
              10 largest companies in {s.name} by market cap
            </div>
            <ConstituentsTable rows={s.top!} />
          </td>
        </tr>
      )}
    </Fragment>
  )
}

export default function SectorsPage() {
  const { sectors, error } = useSectors()

  if (error) {
    return (
      <p className="border border-dashed border-hair bg-raised px-4 py-8 text-center text-sm text-muted">
        No sector data yet — it is generated by the daily scan.
      </p>
    )
  }
  if (!sectors) return <p className="py-8 text-center text-muted">Loading…</p>

  const leaders = sectors.sectors.filter((s) => s.state === 'leading' || s.state === 'improving')
  const laggards = sectors.sectors.filter((s) => s.state === 'lagging' || s.state === 'weakening')

  return (
    <section className="space-y-4">
      <SectionHeading
        title="Sector rotation — where money is flowing"
        right={
          <span className="text-xs text-muted">
            US sectors (SPDR ETFs) vs {sectors.benchmark.symbol} · bar {sectors.bar_date}
          </span>
        }
      />

      {/* Trending / Sinking summary */}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="bg-up/[0.06] p-4 ring-1 ring-up/20">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-up">
            <span className="text-base">▲</span> Trending — money flowing in
          </div>
          <div className="flex flex-wrap gap-1.5">
            {leaders.map((s) => (
              <span key={s.symbol} className="tnum bg-raised px-2 py-1 text-xs text-ink-2 ring-1 ring-hair">
                {s.name}{' '}
                <span className={s.rs['1m'] >= 0 ? 'text-up' : 'text-down'}>
                  {s.rs['1m'] >= 0 ? '+' : ''}
                  {s.rs['1m'].toFixed(1)}
                </span>
              </span>
            ))}
            {leaders.length === 0 && <span className="text-xs text-muted">None currently leading</span>}
          </div>
        </div>
        <div className="bg-down/[0.06] p-4 ring-1 ring-down/20">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-down">
            <span className="text-base">▼</span> Sinking — money flowing out
          </div>
          <div className="flex flex-wrap gap-1.5">
            {laggards.map((s) => (
              <span key={s.symbol} className="tnum bg-raised px-2 py-1 text-xs text-ink-2 ring-1 ring-hair">
                {s.name}{' '}
                <span className={s.rs['1m'] >= 0 ? 'text-up' : 'text-down'}>
                  {s.rs['1m'] >= 0 ? '+' : ''}
                  {s.rs['1m'].toFixed(1)}
                </span>
              </span>
            ))}
            {laggards.length === 0 && <span className="text-xs text-muted">None currently lagging</span>}
          </div>
        </div>
      </div>

      {/* Leaderboard + heatmap */}
      <div className={tableWrapCls}>
        <table className="w-full text-left text-[13px]">
          <thead className={theadCls}>
            <tr>
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Sector</th>
              <th className="px-3 py-2">State</th>
              <th className="px-3 py-2 text-right">RS 1m</th>
              <th className="px-3 py-2 text-right">RS 3m</th>
              <th className="px-3 py-2">Trend</th>
              {SECTOR_HORIZONS.map((h) => (
                <th key={h} className="px-3 py-2 text-right">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="tnum divide-y divide-hair">
            {sectors.sectors.map((s) => (
              <SectorLeaderRow key={s.symbol} s={s} />
            ))}
            <tr className="border-t border-hair-strong text-muted">
              <td />
              <td className="px-3 py-2 font-medium text-ink-2">
                {sectors.benchmark.symbol} (market)
              </td>
              <td /><td /><td /><td />
              {SECTOR_HORIZONS.map((h) => {
                const v = sectors.benchmark.chg[h]
                return (
                  <td key={h} className="px-3 py-2 text-right text-muted">
                    {v === null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                  </td>
                )
              })}
            </tr>
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted">
        Click a sector row to expand its 10 largest companies by market cap with
        fundamentals (refreshed by the daily scan; membership and share counts
        come from a periodically refreshed cache).{' '}
        <span className="text-ink-2">RS</span> = relative strength (sector return minus{' '}
        {sectors.benchmark.symbol} return, in percentage points): positive = outperforming the market.
        Rank is a recency-weighted RS blend (50% 1m · 35% 3m · 15% 6m). State follows the sign of
        1m vs 3m RS — leading (both +), improving (1m + / 3m −), weakening (1m − / 3m +), lagging (both −).
        The %-return columns are colored by magnitude. Informational, not investment advice.
      </p>
    </section>
  )
}
