import { useRef, useState } from 'react'
import { useAlerts, usePortfolio, usePrices } from '../hooks/useAlerts'
import { CATEGORY_LABELS } from '../types'
import DirectionBadge from './DirectionBadge'
import {
  addPosition, closePosition, deleteClosed, deletePosition,
  exportPortfolio, importPortfolio, type ClosedTrade, type Position,
} from '../lib/portfolio'
import { tradingViewUrl } from '../lib/tradingview'
import { badgeRing, btnGhost, cellCls, inputCls, rowCls, tableWrapCls, theadCls } from '../lib/ui'
import { MarketBadge } from './AlertTable'
import Chip from './ui/Chip'
import SectionHeading from './ui/SectionHeading'

const today = () => new Date().toISOString().slice(0, 10)

function fmt(v: number, dp = 2): string {
  return v.toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })
}

function Pnl({ value, pct }: { value: number; pct?: number | null }) {
  const cls = value >= 0 ? 'text-up' : 'text-down'
  return (
    <span className={cls}>
      {value >= 0 ? '+' : ''}
      {fmt(value)}
      {pct !== undefined && pct !== null && (
        <span className="ml-1 text-xs opacity-80">
          ({pct >= 0 ? '+' : ''}
          {pct.toFixed(1)}%)
        </span>
      )}
    </span>
  )
}

function AddForm() {
  const [ticker, setTicker] = useState('')
  const [shares, setShares] = useState('')
  const [cost, setCost] = useState('')
  const [date, setDate] = useState(today())

  const valid = ticker.trim() && Number(shares) > 0 && Number(cost) > 0 && date
  return (
    <div className="flex flex-wrap items-end gap-2 bg-raised p-3 ring-1 ring-hair">
      <div className="w-28">
        <label className="mb-1 block text-[10px] uppercase tracking-wider text-muted">Ticker</label>
        <input className={`w-full ${inputCls}`} value={ticker} placeholder="AAPL"
               onChange={(e) => setTicker(e.target.value.toUpperCase())} />
      </div>
      <div className="w-24">
        <label className="mb-1 block text-[10px] uppercase tracking-wider text-muted">Shares</label>
        <input className={`w-full ${inputCls}`} type="number" min="0" step="any" value={shares}
               onChange={(e) => setShares(e.target.value)} />
      </div>
      <div className="w-28">
        <label className="mb-1 block text-[10px] uppercase tracking-wider text-muted">Avg cost</label>
        <input className={`w-full ${inputCls}`} type="number" min="0" step="any" value={cost}
               onChange={(e) => setCost(e.target.value)} />
      </div>
      <div className="w-36">
        <label className="mb-1 block text-[10px] uppercase tracking-wider text-muted">Buy date</label>
        <input className={`w-full ${inputCls}`} type="date" value={date} max={today()}
               onChange={(e) => setDate(e.target.value)} />
      </div>
      <button
        disabled={!valid}
        onClick={() => {
          const t = ticker.trim()
          addPosition({
            ticker: t,
            market: t.endsWith('.IS') ? 'bist' : t.endsWith('.DE') ? 'de' : 'us',
            shares: Number(shares), avg_cost: Number(cost), date,
          })
          setTicker(''); setShares(''); setCost(''); setDate(today())
        }}
        className={`px-4 py-1.5 text-sm font-medium disabled:opacity-40 ${badgeRing.accent} hover:bg-accent/20`}
      >
        Add position
      </button>
    </div>
  )
}

function CloseDialog({ pos, onDone }: { pos: Position; onDone: () => void }) {
  const [price, setPrice] = useState('')
  const [date, setDate] = useState(today())
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input className={`${inputCls} w-24`} type="number" min="0" step="any" placeholder="Sell price"
             value={price} onChange={(e) => setPrice(e.target.value)} autoFocus />
      <input className={`${inputCls} w-36`} type="date" value={date} max={today()}
             onChange={(e) => setDate(e.target.value)} />
      <button
        disabled={!(Number(price) > 0)}
        onClick={() => { closePosition(pos.id, Number(price), date); onDone() }}
        className={`px-3 py-1.5 text-xs font-medium disabled:opacity-40 ${badgeRing.up} hover:bg-up/20`}
      >
        Confirm sell
      </button>
      <button onClick={onDone} className="text-xs text-muted hover:text-ink">cancel</button>
    </div>
  )
}

function Performance({ closed }: { closed: ClosedTrade[] }) {
  if (closed.length === 0) return null
  const trades = [...closed].sort((a, b) => a.sell_date.localeCompare(b.sell_date))
  const pnls = trades.map((t) => t.shares * (t.sell_price - t.avg_cost))
  const wins = pnls.filter((v) => v > 0)
  const losses = pnls.filter((v) => v <= 0)
  let running = 0
  const cum = pnls.map((v) => (running += v))
  const best = trades[pnls.indexOf(Math.max(...pnls))]
  const worst = trades[pnls.indexOf(Math.min(...pnls))]

  const w = 560
  const h = 48
  const min = Math.min(0, ...cum)
  const max = Math.max(0, ...cum)
  const span = max - min || 1
  const x = (i: number) => (cum.length === 1 ? w : (i / (cum.length - 1)) * w)
  const y = (v: number) => h - ((v - min) / span) * (h - 6) - 3
  const pts = cum.map((v, i) => `${x(i)},${y(v)}`).join(' ')
  const final = cum[cum.length - 1]

  return (
    <div className="space-y-3 bg-raised p-3.5 ring-1 ring-hair">
      <div className="flex flex-wrap gap-2.5">
        <Chip label="Trades" value={trades.length} />
        <Chip label="Win rate" value={`${((wins.length / trades.length) * 100).toFixed(0)}%`}
              tone={wins.length >= losses.length ? 'up' : 'down'} />
        <Chip label="Avg win" value={wins.length ? `+${fmt(wins.reduce((a, b) => a + b, 0) / wins.length)}` : '—'}
              tone={wins.length ? 'up' : 'default'} />
        <Chip label="Avg loss" value={losses.length ? fmt(losses.reduce((a, b) => a + b, 0) / losses.length) : '—'}
              tone={losses.length ? 'down' : 'default'} />
        <Chip label="Best" value={best ? `${best.ticker} ${pnls[trades.indexOf(best)] >= 0 ? '+' : ''}${fmt(pnls[trades.indexOf(best)])}` : '—'}
              tone={pnls[trades.indexOf(best)] >= 0 ? 'up' : 'down'} />
        <Chip label="Worst" value={worst ? `${worst.ticker} ${pnls[trades.indexOf(worst)] >= 0 ? '+' : ''}${fmt(pnls[trades.indexOf(worst)])}` : '—'}
              tone={pnls[trades.indexOf(worst)] < 0 ? 'down' : 'up'} />
      </div>
      {cum.length >= 2 && (
        <div>
          <div className="mb-1 flex items-center justify-between text-xs text-muted">
            <span>Cumulative realized P&L over time</span>
            <span className={final >= 0 ? 'text-up' : 'text-down'}>
              {final >= 0 ? '+' : ''}
              {fmt(final)}
            </span>
          </div>
          <svg viewBox={`0 0 ${w} ${h}`} className="h-12 w-full" preserveAspectRatio="none"
               role="img" aria-label="Cumulative realized profit and loss by trade close date">
            <line x1="0" x2={w} y1={y(0)} y2={y(0)} className="stroke-hair" strokeDasharray="4 4" />
            <polyline points={pts} fill="none"
                      className={final >= 0 ? 'stroke-up' : 'stroke-down'} strokeWidth="2" />
          </svg>
          <div className="flex justify-between text-[10px] text-faint">
            <span>{trades[0].sell_date}</span>
            <span>{trades[trades.length - 1].sell_date}</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default function PortfolioPage() {
  const { positions, closed } = usePortfolio()
  const prices = usePrices()
  const { latest } = useAlerts()
  const [closing, setClosing] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const [live, setLive] = useState<Record<string, number> | null>(null)
  const [liveAt, setLiveAt] = useState<string | null>(null)
  const [updating, setUpdating] = useState(false)
  const [priceNote, setPriceNote] = useState<string | null>(null)

  const priceOf = (t: string) => live?.[t] ?? prices?.prices[t]?.close ?? null

  async function updatePrices() {
    const tickers = [...new Set(positions.map((p) => p.ticker))]
    if (tickers.length === 0) return
    setUpdating(true)
    setPriceNote(null)
    try {
      const r = await fetch(
        `/.netlify/functions/quotes?symbols=${encodeURIComponent(tickers.join(','))}`,
      )
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const j = await r.json()
      const map: Record<string, number> = {}
      for (const [k, v] of Object.entries(j.prices ?? {})) {
        map[k] = (v as { price: number }).price
      }
      if (Object.keys(map).length === 0) throw new Error('no quotes')
      setLive(map)
      setLiveAt(new Date().toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }))
      const missing = tickers.filter((t) => !(t in map))
      setPriceNote(missing.length > 0 ? `no live quote for ${missing.join(', ')} — using last scan` : null)
    } catch {
      setPriceNote('Live quotes unavailable (they work on the deployed site) — showing last-scan prices.')
    } finally {
      setUpdating(false)
    }
  }

  let totalCost = 0
  let totalValue = 0
  let valuedAll = true
  for (const p of positions) {
    totalCost += p.shares * p.avg_cost
    const px = priceOf(p.ticker)
    if (px === null) valuedAll = false
    else totalValue += p.shares * px
  }
  const unrealized = totalValue - (valuedAll ? totalCost : positions
    .filter((p) => priceOf(p.ticker) !== null)
    .reduce((s, p) => s + p.shares * p.avg_cost, 0))
  const realized = closed.reduce((s, t) => s + t.shares * (t.sell_price - t.avg_cost), 0)

  // Today's warning-side signals on stocks you actually hold: bearish crosses
  // and the RSI>75 take-profit alert matter MORE once you own the name.
  const heldTickers = new Set(positions.map((p) => p.ticker))
  const holdingSignals = (latest?.alerts ?? []).filter(
    (a) => heldTickers.has(a.ticker) &&
           (a.direction === 'bearish' || a.category === 'rsi_extended'),
  )

  return (
    <section className="space-y-4">
      <SectionHeading
        title="Portfolio — trade backlog"
        right={
          <span className="flex flex-wrap items-center gap-3">
            <span className="text-xs text-muted">
              {liveAt
                ? `live prices · ${liveAt}`
                : `prices from last scan${prices ? ` (${Object.values(prices.bar_dates).join(' / ')})` : ''}`}
            </span>
            <button
              onClick={updatePrices}
              disabled={updating || positions.length === 0}
              className={`px-3 py-1.5 text-xs font-medium disabled:opacity-40 ${badgeRing.accent} hover:bg-accent/20`}
            >
              {updating ? 'Updating…' : '↻ Update prices'}
            </button>
          </span>
        }
      />
      {priceNote && <p className="text-xs text-accent">{priceNote}</p>}

      <div className="flex flex-wrap gap-2.5">
        <Chip label="Open positions" value={positions.length} />
        <Chip label="Cost basis" value={fmt(totalCost)} />
        <Chip label="Market value" value={valuedAll ? fmt(totalValue) : `${fmt(totalValue)}*`} />
        <Chip label="Unrealized P&L" value={<Pnl value={unrealized} />}
              tone={unrealized >= 0 ? 'up' : 'down'} />
        <Chip label="Realized P&L" value={<Pnl value={realized} />}
              tone={realized >= 0 ? 'up' : 'down'} />
      </div>

      {holdingSignals.length > 0 && (
        <div className="bg-down/[0.06] p-3 ring-1 ring-down/20">
          <div className="mb-1.5 text-sm font-medium text-down">
            ⚠ Signals on your holdings — {latest?.bar_date}
          </div>
          <div className="flex flex-wrap gap-2">
            {holdingSignals.map((a) => (
              <span key={`${a.rule}-${a.ticker}`}
                    title={a.verdict_reason}
                    className="tnum flex items-center gap-2 bg-raised px-2.5 py-1 text-xs text-ink-2 ring-1 ring-hair">
                <span className="font-semibold text-ink">{a.ticker}</span>
                <DirectionBadge direction={a.direction} />
                {CATEGORY_LABELS[a.category] ?? a.category}
              </span>
            ))}
          </div>
        </div>
      )}

      <AddForm />

      {positions.length > 0 ? (
        <div className={tableWrapCls}>
          <table className="w-full text-left text-[13px]">
            <thead className={theadCls}>
              <tr>
                <th className={cellCls}>Ticker</th>
                <th className={`${cellCls} text-right`}>Shares</th>
                <th className={`${cellCls} text-right`}>Avg cost</th>
                <th className={cellCls}>Buy date</th>
                <th className={`${cellCls} text-right`}>Last close</th>
                <th className={`${cellCls} text-right`}>Target</th>
                <th className={`${cellCls} text-right`}>Value</th>
                <th className={`${cellCls} text-right`}>P&L</th>
                <th className={cellCls}>Actions</th>
              </tr>
            </thead>
            <tbody className="tnum divide-y divide-hair">
              {positions.map((p) => {
                const px = priceOf(p.ticker)
                const value = px !== null ? p.shares * px : null
                const pnl = value !== null ? value - p.shares * p.avg_cost : null
                const pnlPct = pnl !== null ? (pnl / (p.shares * p.avg_cost)) * 100 : null
                return (
                  <tr key={p.id} className={rowCls}>
                    <td className={cellCls}>
                      <a href={tradingViewUrl(p.ticker)} target="_blank" rel="noreferrer"
                         className="font-semibold text-info hover:underline">
                        {p.ticker} ↗
                      </a>
                      <MarketBadge market={p.market} />
                    </td>
                    <td className={`${cellCls} text-right text-ink`}>{p.shares}</td>
                    <td className={`${cellCls} text-right text-ink`}>{fmt(p.avg_cost)}</td>
                    <td className={`${cellCls} text-muted`}>{p.date}</td>
                    <td className={`${cellCls} text-right text-ink`}>
                      {px !== null ? fmt(px) : <span className="text-faint">n/a</span>}
                    </td>
                    <td className={`${cellCls} text-right`}>
                      {p.target_mean && px !== null ? (
                        px >= p.target_mean ? (
                          <span className="cursor-help text-up"
                                title={`Analyst mean target ${fmt(p.target_mean)} reached (as of ${p.target_as_of ?? 'add date'})`}>
                            🎯 {fmt(p.target_mean)}
                          </span>
                        ) : (
                          <span className="cursor-help text-ink-2"
                                title={`Analyst mean target as of ${p.target_as_of ?? 'add date'}`}>
                            {fmt(p.target_mean)}
                            <span className="ml-1 text-xs text-muted">
                              (+{((p.target_mean / px - 1) * 100).toFixed(1)}%)
                            </span>
                          </span>
                        )
                      ) : (
                        <span className="text-faint">—</span>
                      )}
                    </td>
                    <td className={`${cellCls} text-right text-ink`}>
                      {value !== null ? fmt(value) : '—'}
                    </td>
                    <td className={`${cellCls} text-right`}>
                      {pnl !== null ? <Pnl value={pnl} pct={pnlPct} /> : '—'}
                    </td>
                    <td className={cellCls}>
                      {closing === p.id ? (
                        <CloseDialog pos={p} onDone={() => setClosing(null)} />
                      ) : (
                        <span className="flex gap-3 text-xs">
                          <button onClick={() => setClosing(p.id)}
                                  className="text-up hover:underline">sell</button>
                          <button onClick={() => deletePosition(p.id)}
                                  className="text-muted hover:text-down">delete</button>
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="border border-dashed border-hair bg-raised px-4 py-8 text-center text-sm text-muted">
          No open positions — add one above, or from a Buy card on the Buys tab.
        </p>
      )}

      <h3 className="flex items-center gap-2 pt-2 text-sm font-semibold text-ink">
        <span className="h-3.5 w-1 bg-muted" />
        Closed trades ({closed.length}) — historic P&L
      </h3>
      <Performance closed={closed} />
      {closed.length > 0 ? (
        <div className={tableWrapCls}>
          <table className="w-full text-left text-[13px]">
            <thead className={theadCls}>
              <tr>
                <th className={cellCls}>Ticker</th>
                <th className={`${cellCls} text-right`}>Shares</th>
                <th className={`${cellCls} text-right`}>Buy</th>
                <th className={`${cellCls} text-right`}>Sell</th>
                <th className={cellCls}>Held</th>
                <th className={`${cellCls} text-right`}>Realized P&L</th>
                <th className={cellCls} />
              </tr>
            </thead>
            <tbody className="tnum divide-y divide-hair">
              {closed.map((t: ClosedTrade) => {
                const pnl = t.shares * (t.sell_price - t.avg_cost)
                const pct = ((t.sell_price - t.avg_cost) / t.avg_cost) * 100
                return (
                  <tr key={t.id} className={rowCls}>
                    <td className={cellCls}>
                      <a href={tradingViewUrl(t.ticker)} target="_blank" rel="noreferrer"
                         className="font-semibold text-info hover:underline">{t.ticker} ↗</a>
                      <MarketBadge market={t.market} />
                    </td>
                    <td className={`${cellCls} text-right text-ink`}>{t.shares}</td>
                    <td className={`${cellCls} text-right text-ink-2`}>
                      {fmt(t.avg_cost)} <span className="text-xs text-muted">{t.date}</span>
                    </td>
                    <td className={`${cellCls} text-right text-ink-2`}>
                      {fmt(t.sell_price)} <span className="text-xs text-muted">{t.sell_date}</span>
                    </td>
                    <td className={`${cellCls} text-muted`}>
                      {Math.max(1, Math.round(
                        (new Date(t.sell_date).getTime() - new Date(t.date).getTime()) / 86400000,
                      ))}d
                    </td>
                    <td className={`${cellCls} text-right`}><Pnl value={pnl} pct={pct} /></td>
                    <td className={`${cellCls} text-right`}>
                      <button onClick={() => deleteClosed(t.id)}
                              className="text-xs text-faint hover:text-down">delete</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted">No closed trades yet — sell a position to log it here.</p>
      )}

      <div className="flex flex-wrap items-center gap-3 border-t border-hair pt-3 text-xs text-muted">
        <button
          onClick={() => {
            const blob = new Blob([exportPortfolio()], { type: 'application/json' })
            const a = document.createElement('a')
            a.href = URL.createObjectURL(blob)
            a.download = `portfolio-backup-${today()}.json`
            a.click()
            URL.revokeObjectURL(a.href)
          }}
          className={btnGhost}
        >
          Export backup
        </button>
        <button onClick={() => fileRef.current?.click()} className={btnGhost}>
          Import backup
        </button>
        <input ref={fileRef} type="file" accept="application/json" className="hidden"
               onChange={async (e) => {
                 const f = e.target.files?.[0]
                 if (f && !importPortfolio(await f.text())) alert('Invalid backup file')
                 e.target.value = ''
               }} />
        <span>
          Positions live only in this browser's storage — export a backup before clearing
          browser data or switching machines. * = some tickers priced n/a (outside the scan universe).
        </span>
      </div>
    </section>
  )
}
