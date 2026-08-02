import { useState } from 'react'
import { inputCls } from '../lib/ui'
import SectionHeading from './ui/SectionHeading'

// Everything on this page is client-side arithmetic — nothing is fetched,
// stored, or sent anywhere. Price formatting follows the site convention.
const fmtPx = (v: number) => (Math.abs(v) >= 10 ? v.toFixed(2) : v.toFixed(4))

const LADDER_STEPS = [0.5, 1, 2, 3, 5, 10]

function PercentLevels() {
  const [price, setPrice] = useState('')
  const [pct, setPct] = useState('1')
  const p = Number(price)
  const q = Number(pct)
  const ok = p > 0 && Number.isFinite(q) && q !== 0
  const steps = ok
    ? [...new Set([Math.abs(q), ...LADDER_STEPS])].sort((a, b) => a - b)
    : LADDER_STEPS

  return (
    <div className="bg-raised p-4 ring-1 ring-hair">
      <div className="mb-1 text-sm font-medium text-ink">Percentage levels</div>
      <p className="mb-3 text-xs text-muted">
        Enter a price and a percent — get the up/down levels for orders.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-32">
          <label className="mb-1 block text-[10px] uppercase tracking-wider text-muted">Price</label>
          <input className={`w-full ${inputCls}`} type="number" min="0" step="any"
                 placeholder="e.g. 228.40" value={price} autoFocus
                 onChange={(e) => setPrice(e.target.value)} />
        </div>
        <div className="w-24">
          <label className="mb-1 block text-[10px] uppercase tracking-wider text-muted">Percent</label>
          <input className={`w-full ${inputCls}`} type="number" min="0" step="any"
                 value={pct} onChange={(e) => setPct(e.target.value)} />
        </div>
        {ok && (
          <div className="tnum flex flex-wrap items-baseline gap-x-4 pb-1 text-sm">
            <span>
              <span className="mr-1 text-xs text-down">−{Math.abs(q)}%</span>
              <span className="font-medium text-ink">{fmtPx(p * (1 - Math.abs(q) / 100))}</span>
            </span>
            <span>
              <span className="mr-1 text-xs text-up">+{Math.abs(q)}%</span>
              <span className="font-medium text-ink">{fmtPx(p * (1 + Math.abs(q) / 100))}</span>
            </span>
          </div>
        )}
      </div>

      {p > 0 && (
        <table className="mt-4 w-full max-w-md text-sm">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-muted">
              <th className="py-1 font-medium">Step</th>
              <th className="py-1 text-right font-medium">Down</th>
              <th className="py-1 text-right font-medium">Up</th>
            </tr>
          </thead>
          <tbody className="tnum divide-y divide-hair">
            {steps.map((s) => (
              <tr key={s} className={ok && s === Math.abs(q) ? 'bg-accent/10' : ''}>
                <td className="py-1 text-muted">{s}%</td>
                <td className="py-1 text-right text-down">{fmtPx(p * (1 - s / 100))}</td>
                <td className="py-1 text-right text-up">{fmtPx(p * (1 + s / 100))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function PercentChange() {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const a = Number(from)
  const b = Number(to)
  const ok = a > 0 && b > 0
  const chg = ok ? (b / a - 1) * 100 : 0

  return (
    <div className="bg-raised p-4 ring-1 ring-hair">
      <div className="mb-1 text-sm font-medium text-ink">Change between two prices</div>
      <p className="mb-3 text-xs text-muted">
        From entry to target/current — what percent move is that?
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-32">
          <label className="mb-1 block text-[10px] uppercase tracking-wider text-muted">From</label>
          <input className={`w-full ${inputCls}`} type="number" min="0" step="any"
                 placeholder="e.g. 100" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div className="w-32">
          <label className="mb-1 block text-[10px] uppercase tracking-wider text-muted">To</label>
          <input className={`w-full ${inputCls}`} type="number" min="0" step="any"
                 placeholder="e.g. 112.5" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
        {ok && (
          <div className="tnum flex flex-wrap items-baseline gap-x-4 pb-1 text-sm">
            <span className={`font-medium ${chg >= 0 ? 'text-up' : 'text-down'}`}>
              {chg >= 0 ? '+' : ''}{chg.toFixed(2)}%
            </span>
            <span className="text-xs text-muted">
              Δ {fmtPx(b - a)} · back to breakeven needs{' '}
              <span className="text-ink-2">
                {a === b ? '0.00' : ((a / b - 1) * 100 >= 0 ? '+' : '') + ((a / b - 1) * 100).toFixed(2)}%
              </span>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ToolsPage() {
  return (
    <section className="space-y-4">
      <SectionHeading title="Tools — quick calculators" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PercentLevels />
        <PercentChange />
      </div>
      <p className="text-xs text-muted">
        Client-side arithmetic only — nothing here is fetched, stored, or sent anywhere.
      </p>
    </section>
  )
}
