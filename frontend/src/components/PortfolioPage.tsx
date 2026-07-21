import { Fragment, useRef, useState } from 'react'
import { useAlerts, useForex, useHealth, usePortfolio, usePrices, useTargets, useTrackRecord } from '../hooks/useAlerts'
import { usePortfolioSync, type SyncStatus } from '../hooks/usePortfolioSync'
import { assessHealth, HEALTH_DOT, type HealthLevel } from '../lib/health'
import { CATEGORY_LABELS, type AlertHistory, type TargetsData, type TrackRecordData } from '../types'
import DirectionBadge from './DirectionBadge'
import Tabs, { type TabItem } from './ui/Tabs'
import {
  addPosition, closePosition, deleteClosed, deletePosition,
  exportPortfolio, importPortfolio, updatePosition,
  type ClosedTrade, type Position,
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

// Each market trades in its own currency — positions store native amounts
// (BIST avg costs are lira, DE are euro). Totals convert via the daily FX
// snapshot (forex.json EURUSD/TRYUSD) into a chosen display currency.
const MARKET_CCY: Record<string, string> = { us: 'USD', de: 'EUR', bist: 'TRY' }
const CCY_SYM: Record<string, string> = { USD: '$', EUR: '€', TRY: '₺' }
type DisplayCcy = 'USD' | 'TRY'
const CCY_ITEMS: TabItem<DisplayCcy>[] = [
  { value: 'USD', label: '$ USD', tone: 'info' },
  { value: 'TRY', label: '₺ TRY', tone: 'info' },
]

const ccyOf = (market?: string) => MARKET_CCY[market ?? 'us'] ?? 'USD'

function readDisplayCcy(): DisplayCcy {
  try {
    return localStorage.getItem('ma-portfolio-ccy') === 'TRY' ? 'TRY' : 'USD'
  } catch {
    return 'USD'
  }
}

function Pnl({ value, pct, sym = '' }: { value: number; pct?: number | null; sym?: string }) {
  const cls = value >= 0 ? 'text-up' : 'text-down'
  return (
    <span className={cls}>
      {value >= 0 ? '+' : ''}
      {sym}
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

// Best-known analyst mean target for a position: stored on the position
// (Buy-card add or manual edit) → else the rolling universe cache
// (targets.json, ≤~1 week old, covers all scanned tickers) → else the
// ticker's most recent tracked BUY → else its most recent alert in the
// 30-day history. Display-only resolution; editing stores it explicitly.
function resolveTarget(
  p: Position, targets: TargetsData | null,
  track: TrackRecordData | null, history: AlertHistory | null,
): { value: number; asOf: string; source: string } | null {
  if (p.target_mean)
    return { value: p.target_mean, asOf: p.target_as_of ?? p.date, source: 'saved on position' }
  const cached = targets?.targets[p.ticker]
  if (cached?.target_mean)
    return {
      value: cached.target_mean, asOf: cached.as_of,
      source: cached.n_analysts ? `consensus of ${cached.n_analysts} analysts` : 'analyst consensus',
    }
  const tracked = (track?.entries ?? [])
    .filter((e) => e.ticker === p.ticker && e.target_mean)
    .sort((a, b) => b.entry_date.localeCompare(a.entry_date))[0]
  if (tracked)
    return { value: tracked.target_mean!, asOf: tracked.entry_date, source: 'from tracked alert' }
  for (const d of history?.days ?? []) { // newest first
    for (const a of d.alerts) {
      const t = a.ticker === p.ticker ? a.fundamentals?.analyst?.target_mean : undefined
      if (t) return { value: t, asOf: a.date, source: 'from recent alert' }
    }
  }
  return null
}

function TargetCell({ p, px, targets, track, history }: {
  p: Position; px: number | null; targets: TargetsData | null
  track: TrackRecordData | null; history: AlertHistory | null
}) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState('')
  const resolved = resolveTarget(p, targets, track, history)

  if (editing) {
    return (
      <span className="flex items-center justify-end gap-1.5">
        <input className={`${inputCls} w-24`} type="number" min="0" step="any" autoFocus
               placeholder="target" value={val} onChange={(e) => setVal(e.target.value)} />
        <button
          disabled={!(Number(val) > 0)}
          onClick={() => {
            updatePosition(p.id, { target_mean: Number(val), target_as_of: today() })
            setEditing(false)
          }}
          className="text-xs text-up hover:underline disabled:opacity-40">save</button>
        <button onClick={() => setEditing(false)} className="text-xs text-muted hover:text-ink">×</button>
      </span>
    )
  }
  if (!resolved) {
    return (
      <button onClick={() => { setVal(''); setEditing(true) }}
              className="text-xs text-muted hover:text-ink" title="Set a price target for this position">
        set…
      </button>
    )
  }
  const reached = px !== null && px >= resolved.value
  return (
    <span className="group cursor-help"
          title={`Analyst mean target ${resolved.source} (as of ${resolved.asOf}) — click ✎ to override`}>
      {reached ? (
        <span className="text-up">🎯 {fmt(resolved.value)}</span>
      ) : (
        <span className="text-ink-2">
          {fmt(resolved.value)}
          {px !== null && (
            <span className="ml-1 text-xs text-muted">
              (+{((resolved.value / px - 1) * 100).toFixed(1)}%)
            </span>
          )}
        </span>
      )}
      <button onClick={() => { setVal(String(resolved.value)); setEditing(true) }}
              className="ml-1 text-xs text-muted opacity-0 transition-opacity group-hover:opacity-100 hover:text-ink">
        ✎
      </button>
    </span>
  )
}

const HEALTH_TONE: Record<HealthLevel, string> = {
  strong: 'text-up',
  ok: 'text-muted',
  caution: 'text-accent',
  weak: 'text-down',
}

/** Health cell: a coloured dot + label, click to expand the full reasoning. */
function HealthCell({ h, open, onToggle }: {
  h: ReturnType<typeof assessHealth>
  open: boolean
  onToggle: () => void
}) {
  const quiet = h.level === 'strong' || h.level === 'ok'
  return (
    <button
      onClick={onToggle}
      className={`flex items-center gap-1.5 text-xs ${HEALTH_TONE[h.level]} hover:underline`}
      title={quiet ? 'No warnings — click for detail' : h.reasons.map((r) => `• ${r.text}`).join('\n')}
      aria-expanded={open}
    >
      <span>{HEALTH_DOT[h.level]}</span>
      {h.label}
      {h.reasons.length > 0 && (
        <span className="text-muted">({h.reasons.length})</span>
      )}
    </button>
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

function Performance({ closed, conv, sym }: {
  closed: ClosedTrade[]
  conv: (amount: number, market?: string) => number
  sym: string
}) {
  if (closed.length === 0) return null
  const trades = [...closed].sort((a, b) => a.sell_date.localeCompare(b.sell_date))
  // per-trade P&L converted to the display currency (at today's FX rate)
  const pnls = trades.map((t) => conv(t.shares * (t.sell_price - t.avg_cost), t.market))
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
        <Chip label="Avg win" value={wins.length ? `+${sym}${fmt(wins.reduce((a, b) => a + b, 0) / wins.length)}` : '—'}
              tone={wins.length ? 'up' : 'default'} />
        <Chip label="Avg loss" value={losses.length ? `${sym.length ? '−' + sym : ''}${fmt(Math.abs(losses.reduce((a, b) => a + b, 0) / losses.length))}` : '—'}
              tone={losses.length ? 'down' : 'default'} />
        <Chip label="Best" value={best ? `${best.ticker} ${pnls[trades.indexOf(best)] >= 0 ? '+' : ''}${sym}${fmt(pnls[trades.indexOf(best)])}` : '—'}
              tone={pnls[trades.indexOf(best)] >= 0 ? 'up' : 'down'} />
        <Chip label="Worst" value={worst ? `${worst.ticker} ${pnls[trades.indexOf(worst)] >= 0 ? '+' : ''}${sym}${fmt(pnls[trades.indexOf(worst)])}` : '—'}
              tone={pnls[trades.indexOf(worst)] < 0 ? 'down' : 'up'} />
      </div>
      {cum.length >= 2 && (
        <div>
          <div className="mb-1 flex items-center justify-between text-xs text-muted">
            <span>Cumulative realized P&L over time</span>
            <span className={final >= 0 ? 'text-up' : 'text-down'}>
              {final >= 0 ? '+' : ''}
              {sym}
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

function syncedAgo(iso: string | null): string {
  if (!iso) return ''
  const secs = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 1000))
  if (secs < 45) return 'just now'
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`
  return iso.slice(0, 10)
}

const SYNC_TONE: Record<SyncStatus, string> = {
  off: 'text-muted',
  syncing: 'text-accent',
  synced: 'text-up',
  error: 'text-down',
}

function SyncPanel() {
  const { code, status, lastSyncedAt, error, enable, connect, disconnect, syncNow } =
    usePortfolioSync()
  const [input, setInput] = useState('')
  const [reveal, setReveal] = useState(false)
  const [copied, setCopied] = useState(false)
  const busy = status === 'syncing'

  const statusLabel =
    status === 'syncing'
      ? 'Syncing…'
      : status === 'error'
        ? 'Offline'
        : status === 'synced'
          ? `Synced${lastSyncedAt ? ` · ${syncedAgo(lastSyncedAt)}` : ''}`
          : ''

  if (!code) {
    return (
      <div className="space-y-2 border-t border-hair pt-3 text-xs text-muted">
        <div className="text-sm font-medium text-ink">Sync across devices</div>
        <p>
          Your portfolio is saved only in this browser. Enable sync to see the same
          positions on your phone and other computers — free, no account needed.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => enable()} className={btnGhost} disabled={busy}>
            {busy ? 'Enabling…' : 'Enable sync'}
          </button>
          <span>or</span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="paste an existing sync code"
            className={`${inputCls} w-56`}
          />
          <button
            onClick={() => connect(input)}
            className={btnGhost}
            disabled={!input.trim() || busy}
          >
            Connect
          </button>
        </div>
        {error && <p className="text-down">{error}</p>}
      </div>
    )
  }

  return (
    <div className="space-y-2 border-t border-hair pt-3 text-xs text-muted">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-ink">Sync across devices</span>
        {statusLabel && <span className={SYNC_TONE[status]}>{statusLabel}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span>Sync code</span>
        <code className="tnum rounded bg-inset px-2 py-0.5 text-ink">
          {reveal ? code : '••••••••••••'}
        </code>
        <button onClick={() => setReveal((r) => !r)} className="hover:text-ink">
          {reveal ? 'hide' : 'show'}
        </button>
        <button
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(code)
              setCopied(true)
              setTimeout(() => setCopied(false), 1500)
            } catch {
              setReveal(true) // clipboard blocked — at least reveal it to copy by hand
            }
          }}
          className="text-accent hover:underline"
        >
          {copied ? 'copied ✓' : 'copy'}
        </button>
        <button onClick={() => syncNow()} className={btnGhost} disabled={busy}>
          Sync now
        </button>
        <button onClick={() => disconnect()} className="text-faint hover:text-down">
          disconnect
        </button>
      </div>
      <p>
        Enter this code on another device under Portfolio → Sync to load the same
        portfolio. Anyone with the code can view and edit it, so keep it private — it is
        the only key to your data.
      </p>
      {error && <p className="text-down">{error}</p>}
    </div>
  )
}

export default function PortfolioPage() {
  const { positions, closed } = usePortfolio()
  const prices = usePrices()
  const { latest, history } = useAlerts()
  const { track } = useTrackRecord()
  const targets = useTargets()
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

  const health = useHealth()
  const [openHealth, setOpenHealth] = useState<string | null>(null)
  const { forex } = useForex()
  const [dispCcy, setDispCcyState] = useState<DisplayCcy>(readDisplayCcy)
  const setDispCcy = (c: DisplayCcy) => {
    setDispCcyState(c)
    try { localStorage.setItem('ma-portfolio-ccy', c) } catch { /* fine */ }
  }

  // USD value of 1 unit of a currency, from the daily forex snapshot
  const usdPer = (code: string): number | null =>
    code === 'USD' ? 1 : forex?.currencies.find((c) => c.code === code)?.vs_usd?.price ?? null

  const neededCcys = [...new Set([...positions, ...closed].map((p) => ccyOf(p.market)))]
  const fxOk = usdPer(dispCcy) !== null && neededCcys.every((c) => usdPer(c) !== null)

  // native amount in a market's currency → the display currency; identity
  // fallback when a rate is missing (totals then carry a * note)
  const conv = (amount: number, market?: string): number => {
    const from = usdPer(ccyOf(market))
    const to = usdPer(dispCcy)
    return fxOk && from !== null && to !== null ? (amount * from) / to : amount
  }
  const sym = CCY_SYM[dispCcy]

  let totalCost = 0
  let totalValue = 0
  let valuedAll = true
  for (const p of positions) {
    totalCost += conv(p.shares * p.avg_cost, p.market)
    const px = priceOf(p.ticker)
    if (px === null) valuedAll = false
    else totalValue += conv(p.shares * px, p.market)
  }
  const unrealized = totalValue - (valuedAll ? totalCost : positions
    .filter((p) => priceOf(p.ticker) !== null)
    .reduce((s, p) => s + conv(p.shares * p.avg_cost, p.market), 0))
  const realized = closed.reduce((s, t) => s + conv(t.shares * (t.sell_price - t.avg_cost), t.market), 0)

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

      <div className="flex flex-wrap items-center gap-2.5">
        <Chip label="Open positions" value={positions.length} />
        <Chip label="Cost basis" value={`${sym}${fmt(totalCost)}`} />
        <Chip label="Market value"
              value={`${sym}${fmt(totalValue)}${valuedAll && fxOk ? '' : '*'}`} />
        <Chip label="Unrealized P&L" value={<Pnl value={unrealized} sym={sym} />}
              tone={unrealized >= 0 ? 'up' : 'down'} />
        <Chip label="Realized P&L" value={<Pnl value={realized} sym={sym} />}
              tone={realized >= 0 ? 'up' : 'down'} />
        <Tabs items={CCY_ITEMS} active={dispCcy} onChange={setDispCcy} size="sm" />
      </div>
      {fxOk ? (
        <p className="tnum flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <span className="text-ink-2">FX used for totals</span>
          {(['EUR', 'TRY'] as const).map((code) => {
            const usd = usdPer(code)
            if (usd === null) return null
            // show the pair the way each is normally quoted: EURUSD, USDTRY
            const asPair = code === 'EUR'
              ? `EUR/USD ${usd.toFixed(4)}`
              : `USD/TRY ${(1 / usd).toFixed(2)}`
            return (
              <span key={code} className="cursor-help"
                    title={`1 ${code} = $${usd.toFixed(4)} — used to convert ${code} positions into ${dispCcy} totals`}>
                {asPair}
              </span>
            )
          })}
          <span className="text-faint">
            · daily scan{forex?.bar_date ? ` ${forex.bar_date}` : ''} · totals in {dispCcy}
          </span>
        </p>
      ) : (
        <p className="text-xs text-accent">
          * FX rates unavailable — totals are a raw mixed-currency sum until the next scan.
        </p>
      )}

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
                <th className={cellCls}>Health</th>
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
                const rowSym = CCY_SYM[ccyOf(p.market)] ?? ''
                const hv = assessHealth(health?.tickers[p.ticker])
                const hOpen = openHealth === p.id
                return (
                  <Fragment key={p.id}>
                  <tr className={rowCls}>
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
                    <td className={cellCls}>
                      <HealthCell h={hv} open={hOpen}
                                  onToggle={() => setOpenHealth(hOpen ? null : p.id)} />
                    </td>
                    <td className={`${cellCls} text-right text-ink`}>
                      {px !== null ? fmt(px) : <span className="text-faint">n/a</span>}
                    </td>
                    <td className={`${cellCls} text-right`}>
                      <TargetCell p={p} px={px} targets={targets} track={track} history={history} />
                    </td>
                    <td className={`${cellCls} text-right text-ink`}>
                      {value !== null ? `${rowSym}${fmt(value)}` : '—'}
                    </td>
                    <td className={`${cellCls} text-right`}>
                      {pnl !== null ? <Pnl value={pnl} pct={pnlPct} sym={rowSym} /> : '—'}
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
                  {hOpen && (
                    <tr>
                      <td colSpan={9} className="bg-inset px-4 pb-3 pt-2">
                        <div className="text-xs">
                          <div className="mb-1 font-medium text-ink">
                            {p.ticker} — position health
                          </div>
                          {hv.reasons.length > 0 ? (
                            <ul className="space-y-0.5">
                              {hv.reasons.map((r, i) => (
                                <li key={i} className={r.severity === 2 ? 'text-down' : 'text-accent'}>
                                  {r.severity === 2 ? '▼' : '▲'} {r.text}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-muted">No warning signs in today's data.</p>
                          )}
                          {hv.positives.length > 0 && (
                            <ul className="mt-1 space-y-0.5">
                              {hv.positives.map((t, i) => (
                                <li key={i} className="text-up">● {t}</li>
                              ))}
                            </ul>
                          )}
                          <p className="mt-1.5 text-faint">
                            Caution indicator only — backtests (docs/EXITS.md) found stop-loss and
                            SMA-exit rules underperformed simply holding; RSI&gt;75 was the one
                            exit hint that helped. Judge for yourself.
                          </p>
                        </div>
                      </td>
                    </tr>
                  )}
                  </Fragment>
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
      <Performance closed={closed} conv={conv} sym={sym} />
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
                const rowSym = CCY_SYM[ccyOf(t.market)] ?? ''
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
                    <td className={`${cellCls} text-right`}><Pnl value={pnl} pct={pct} sym={rowSym} /></td>
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

      <SyncPanel />

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
          browser data or switching machines. * = some tickers priced n/a (outside the scan
          universe) or FX unavailable. Per-row amounts are in each stock's own currency
          ($ / € / ₺); the summary totals convert everything to {dispCcy} using the daily FX
          snapshot{forex?.bar_date ? ` (bar ${forex.bar_date})` : ''}.
        </span>
      </div>
    </section>
  )
}
