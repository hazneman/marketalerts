import type { ScanResult } from '../types'
import Chip from './ui/Chip'

function staleBarWarning(barDate: string): boolean {
  // The bar should never be older than ~4 calendar days (long weekend + holiday)
  const ageDays = (Date.now() - new Date(barDate + 'T21:00:00Z').getTime()) / 86400000
  return ageDays > 4
}

export default function ScanStatus({ latest }: { latest: ScanResult }) {
  const failed = latest.failures.length
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
          tone={staleBarWarning(d) ? 'warn' : 'default'}
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
