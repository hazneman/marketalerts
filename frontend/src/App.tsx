import { useMemo, useState } from 'react'
import CategorySection from './components/CategorySection'
import FilterBar, { type DirectionFilter } from './components/FilterBar'
import ScanStatus from './components/ScanStatus'
import { useAlerts } from './hooks/useAlerts'
import { CATEGORY_LABELS, type AlertItem } from './types'

export default function App() {
  const { latest, history, error } = useAlerts()
  const [search, setSearch] = useState('')
  const [direction, setDirection] = useState<DirectionFilter>('all')
  const [selectedDay, setSelectedDay] = useState('')

  const days = history?.days ?? []
  const activeDay = selectedDay || latest?.bar_date || ''

  const alerts: AlertItem[] = useMemo(() => {
    const source =
      activeDay && activeDay !== latest?.bar_date
        ? days.find((d) => d.bar_date === activeDay)?.alerts ?? []
        : latest?.alerts ?? []
    const q = search.trim().toUpperCase()
    return source.filter(
      (a) =>
        (direction === 'all' || a.direction === direction) &&
        (q === '' || a.ticker.includes(q)),
    )
  }, [latest, days, activeDay, search, direction])

  // Known categories first (stable order), unknown ones appended (future rules)
  const categories = useMemo(() => {
    const known = Object.keys(CATEGORY_LABELS)
    const present = [...new Set(alerts.map((a) => a.category))]
    return [...known, ...present.filter((c) => !known.includes(c))]
  }, [alerts])

  if (error) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-16 text-center text-slate-400">
        <h1 className="mb-3 text-xl font-semibold text-slate-100">Market Alerts</h1>
        <p>
          No scan data yet ({error}). Run a scan first — locally via{' '}
          <code className="text-sky-400">./dev.sh</code>, or wait for the daily
          GitHub Action.
        </p>
      </main>
    )
  }
  if (!latest) {
    return <main className="px-4 py-16 text-center text-slate-500">Loading…</main>
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold text-slate-100">Market Alerts</h1>
        <span className="text-sm text-slate-500">
          US stocks · S&amp;P 500 + Nasdaq 100
        </span>
      </header>

      <ScanStatus latest={latest} />

      <FilterBar
        search={search}
        onSearch={setSearch}
        direction={direction}
        onDirection={setDirection}
        days={days}
        selectedDay={activeDay}
        onDay={setSelectedDay}
      />

      {categories.map((cat) => (
        <CategorySection
          key={cat}
          title={CATEGORY_LABELS[cat] ?? cat}
          alerts={alerts.filter((a) => a.category === cat)}
          barDate={activeDay}
        />
      ))}
    </main>
  )
}
