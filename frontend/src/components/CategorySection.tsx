import type { AlertItem } from '../types'
import AlertTable from './AlertTable'

interface Props {
  title: string
  alerts: AlertItem[]
  barDate: string
}

export default function CategorySection({ title, alerts, barDate }: Props) {
  const bulls = alerts.filter((a) => a.direction === 'bullish').length
  const bears = alerts.length - bulls
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
        {alerts.length > 0 && (
          <span className="flex gap-2 text-xs">
            {bulls > 0 && (
              <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-400">
                {bulls} bull
              </span>
            )}
            {bears > 0 && (
              <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-rose-400">
                {bears} bear
              </span>
            )}
          </span>
        )}
      </div>
      {alerts.length > 0 ? (
        <AlertTable alerts={alerts} />
      ) : (
        <p className="rounded-lg border border-dashed border-slate-800 px-4 py-6 text-center text-sm text-slate-500">
          No crosses on {barDate}
        </p>
      )}
    </section>
  )
}
