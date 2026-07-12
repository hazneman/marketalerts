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
        <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight text-slate-100"><span className="h-4 w-1 rounded-full bg-sky-400/70" />{title}</h2>
        {alerts.length > 0 && (
          <span className="flex gap-2 text-xs">
            {bulls > 0 && (
              <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 font-medium text-emerald-300 ring-1 ring-emerald-400/20">
                {bulls} bull
              </span>
            )}
            {bears > 0 && (
              <span className="rounded-full bg-rose-500/10 px-2 py-0.5 font-medium text-rose-300 ring-1 ring-rose-400/20">
                {bears} bear
              </span>
            )}
          </span>
        )}
      </div>
      {alerts.length > 0 ? (
        <AlertTable alerts={alerts} />
      ) : (
        <p className="rounded-xl border border-dashed border-white/10 bg-white/[0.01] px-4 py-8 text-center text-sm text-slate-500">
          No crosses on {barDate}
        </p>
      )}
    </section>
  )
}
