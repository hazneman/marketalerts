import type { AlertItem } from '../types'
import AlertTable from './AlertTable'
import Badge from './ui/Badge'
import SectionHeading from './ui/SectionHeading'

interface Props {
  title: string
  description?: string // long form of the rule name, shown muted beside the title
  alerts: AlertItem[]
  barDate: string
}

export default function CategorySection({ title, description, alerts, barDate }: Props) {
  const bulls = alerts.filter((a) => a.direction === 'bullish').length
  const bears = alerts.length - bulls
  return (
    <section className="space-y-3">
      <SectionHeading
        title={
          <span className="flex flex-wrap items-center gap-3">
            {title}
            {description && description !== title && (
              <span className="text-sm font-normal text-muted">{description}</span>
            )}
            {alerts.length > 0 && (
              <span className="flex gap-1.5 text-xs">
                {bulls > 0 && <Badge tone="up">{bulls} bull</Badge>}
                {bears > 0 && <Badge tone="down">{bears} bear</Badge>}
              </span>
            )}
          </span>
        }
      />
      {alerts.length > 0 ? (
        <AlertTable alerts={alerts} />
      ) : (
        <p className="border border-dashed border-hair bg-raised px-4 py-8 text-center text-sm text-muted">
          No crosses on {barDate}
        </p>
      )}
    </section>
  )
}
