import type { ReactNode } from 'react'

// KPI stat tile — the single definition (was duplicated in ScanStatus + PortfolioPage).
// `warn` = amber caution, `up`/`down` = signal green/red, default = plain ink.
export default function Chip({
  label,
  value,
  tone = 'default',
  title,
  className = '',
}: {
  label: string
  value: ReactNode
  tone?: 'default' | 'warn' | 'up' | 'down'
  title?: string
  className?: string
}) {
  const surface =
    tone === 'warn' ? 'bg-accent/10 ring-accent/30' : 'bg-raised ring-hair'
  const valueTone =
    tone === 'warn'
      ? 'text-accent'
      : tone === 'up'
        ? 'text-up'
        : tone === 'down'
          ? 'text-down'
          : 'text-ink'
  return (
    <div
      title={title}
      className={`flex min-w-[7rem] flex-col gap-0.5 px-3 py-2 ring-1 ${surface} ${className}`}
    >
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted">{label}</span>
      <span className={`nums text-sm font-semibold ${valueTone}`}>{value}</span>
    </div>
  )
}
