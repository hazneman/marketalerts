import type { ScanResult } from '../types'

function staleBarWarning(barDate: string): boolean {
  // The bar should never be older than ~4 calendar days (long weekend + holiday)
  const ageDays = (Date.now() - new Date(barDate + 'T21:00:00Z').getTime()) / 86400000
  return ageDays > 4
}

export default function ScanStatus({ latest }: { latest: ScanResult }) {
  const failed = latest.failures.length
  const warn = failed > 0 || staleBarWarning(latest.bar_date)
  const scanTime = new Date(latest.generated_at).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
  return (
    <div
      className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border px-4 py-2.5 text-sm ${
        warn
          ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
          : 'border-slate-700 bg-slate-900 text-slate-300'
      }`}
    >
      <span>
        Last scan: <span className="font-medium text-slate-100">{scanTime}</span>
      </span>
      {latest.bar_dates && Object.keys(latest.bar_dates).length > 1 ? (
        <span>
          {Object.entries(latest.bar_dates).map(([m, d], i) => (
            <span key={m}>
              {i > 0 && ' · '}
              {m.toUpperCase()} bar:{' '}
              <span className="font-medium text-slate-100">{d}</span>
            </span>
          ))}
        </span>
      ) : (
        <span>
          Bar date: <span className="font-medium text-slate-100">{latest.bar_date}</span>
        </span>
      )}
      <span>
        {latest.scanned}/{latest.universe_count} scanned
      </span>
      {failed > 0 && (
        <span title={latest.failures.join(', ')}>⚠ {failed} failed</span>
      )}
      {latest.insufficient_history.length > 0 && (
        <span
          className="text-slate-400"
          title={latest.insufficient_history.join(', ')}
        >
          {latest.insufficient_history.length} skipped (short history)
        </span>
      )}
    </div>
  )
}
