import type { ScanResult } from '../types'

function staleBarWarning(barDate: string): boolean {
  // The bar should never be older than ~4 calendar days (long weekend + holiday)
  const ageDays = (Date.now() - new Date(barDate + 'T21:00:00Z').getTime()) / 86400000
  return ageDays > 4
}

function Chip({ label, value, tone = 'default', title }: {
  label: string
  value: string
  tone?: 'default' | 'warn'
  title?: string
}) {
  return (
    <div
      title={title}
      className={`flex min-w-[7rem] flex-col gap-0.5 rounded-xl px-3.5 py-2.5 ring-1 ${
        tone === 'warn'
          ? 'bg-amber-500/10 ring-amber-400/30'
          : 'bg-white/[0.03] ring-white/5'
      }`}
    >
      <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
        {label}
      </span>
      <span
        className={`tnum text-sm font-semibold ${
          tone === 'warn' ? 'text-amber-300' : 'text-slate-100'
        }`}
      >
        {value}
      </span>
    </div>
  )
}

export default function ScanStatus({ latest }: { latest: ScanResult }) {
  const failed = latest.failures.length
  const stale = staleBarWarning(latest.bar_date)
  const scanTime = new Date(latest.generated_at).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
  const barDates =
    latest.bar_dates && Object.keys(latest.bar_dates).length > 1
      ? Object.entries(latest.bar_dates)
      : [['bar', latest.bar_date] as [string, string]]

  return (
    <div className="flex flex-wrap gap-2.5">
      <Chip label="Last scan" value={scanTime} />
      {barDates.map(([m, d]) => (
        <Chip
          key={m}
          label={m === 'bar' ? 'Bar date' : `${m.toUpperCase()} bar`}
          value={d}
          tone={stale ? 'warn' : 'default'}
        />
      ))}
      <Chip label="Scanned" value={`${latest.scanned}/${latest.universe_count}`} />
      {failed > 0 && (
        <Chip label="Failed" value={String(failed)} tone="warn"
              title={latest.failures.join(', ')} />
      )}
      {latest.insufficient_history.length > 0 && (
        <Chip
          label="Short history"
          value={String(latest.insufficient_history.length)}
          title={latest.insufficient_history.join(', ')}
        />
      )}
    </div>
  )
}
