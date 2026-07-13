import { useMemo, useState } from 'react'
import BuysPage from './components/BuysPage'
import CategorySection from './components/CategorySection'
import FilterBar, { type DirectionFilter } from './components/FilterBar'
import ForexPage from './components/ForexPage'
import ScanStatus from './components/ScanStatus'
import { useAlerts } from './hooks/useAlerts'
import { CATEGORY_LABELS, MARKET_ORDER, type AlertItem } from './types'

type Page = 'stocks' | 'buys' | 'forex'

export default function App() {
  const { latest, history, error } = useAlerts()
  const [page, setPage] = useState<Page>('stocks')
  const [search, setSearch] = useState('')
  const [direction, setDirection] = useState<DirectionFilter>('all')
  const [market, setMarket] = useState('all')
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
        (market === 'all' || (a.market ?? 'us') === market) &&
        (q === '' || a.ticker.includes(q)),
    )
  }, [latest, days, activeDay, search, direction, market])

  const marketsPresent = useMemo(
    () =>
      [...new Set((latest?.alerts ?? []).map((a) => a.market ?? 'us'))].sort(
        (a, b) => (MARKET_ORDER[a] ?? 9) - (MARKET_ORDER[b] ?? 9),
      ),
    [latest],
  )

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
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-white/5 bg-slate-950/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5">
              <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden="true">
                <rect width="32" height="32" rx="8" className="fill-sky-500/15" />
                <path
                  d="M5 20l6-7 5 4 5-9 6 8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-sky-400"
                />
              </svg>
              <h1 className="text-lg font-semibold tracking-tight text-white">
                Market Alerts
              </h1>
            </div>
            <nav className="flex rounded-full bg-white/5 p-1 text-sm ring-1 ring-white/10">
              {(['stocks', 'buys', 'forex'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`rounded-full px-3.5 py-1 capitalize transition-colors ${
                    page === p
                      ? 'bg-sky-500/20 font-medium text-sky-300 ring-1 ring-sky-400/30'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {p}
                </button>
              ))}
            </nav>
          </div>
          <span className="hidden text-sm text-slate-500 sm:block">
            {page === 'stocks'
              ? 'S&P 500 + Nasdaq 100 · DAX · BIST'
              : page === 'buys'
                ? 'Signals where all three layers agree'
                : 'Major currencies vs USD'}
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8">

      {page === 'forex' ? (
        <ForexPage />
      ) : page === 'buys' ? (
        <BuysPage />
      ) : (
        <>
          <ScanStatus latest={latest} />

          <FilterBar
            search={search}
            onSearch={setSearch}
            direction={direction}
            onDirection={setDirection}
            days={days}
            selectedDay={activeDay}
            onDay={setSelectedDay}
            markets={marketsPresent}
            market={market}
            onMarket={setMarket}
          />

          {categories.map((cat) => (
            <CategorySection
              key={cat}
              title={CATEGORY_LABELS[cat] ?? cat}
              alerts={alerts.filter((a) => a.category === cat)}
              barDate={activeDay}
            />
          ))}
        </>
      )}
      </main>
    </div>
  )
}
