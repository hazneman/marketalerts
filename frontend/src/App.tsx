import { useMemo, useState } from 'react'
import BuysPage from './components/BuysPage'
import CategorySection from './components/CategorySection'
import FilterBar, { type DirectionFilter } from './components/FilterBar'
import ForexPage from './components/ForexPage'
import PortfolioPage from './components/PortfolioPage'
import ScanStatus from './components/ScanStatus'
import SectorsPage from './components/SectorsPage'
import TrackRecordPage from './components/TrackRecordPage'
import { useAlerts } from './hooks/useAlerts'
import { PortfolioSyncContext, usePortfolioSync } from './hooks/usePortfolioSync'
import Tabs from './components/ui/Tabs'
import ThemeToggle from './components/ui/ThemeToggle'
import { CATEGORY_LABELS, MARKET_ORDER, type AlertItem } from './types'

type Page = 'stocks' | 'buys' | 'sectors' | 'forex' | 'portfolio' | 'track'

const PAGES: Page[] = ['stocks', 'buys', 'sectors', 'forex', 'portfolio', 'track']
const PAGE_LABELS: Record<Page, string> = {
  stocks: 'Stocks',
  buys: 'Buys',
  sectors: 'Sectors',
  forex: 'Forex',
  portfolio: 'Portfolio',
  track: 'Track record',
}
const TAGLINES: Record<Page, string> = {
  stocks: 'S&P 500 + Nasdaq 100 · DAX · BIST',
  buys: 'Signals where all three layers agree',
  sectors: 'US sector rotation vs the market',
  forex: 'Major currencies vs USD',
  portfolio: 'Your trades · stored in this browser',
  track: 'Did the BUY alerts beat their market?',
}

// Footer build stamp — compare this commit against the repo's latest to see
// whether the deployed site is up to date with development. Values are injected
// at build time (vite.config.ts).
function BuildStamp() {
  const t = __BUILD_TIME__
  const when = t.length >= 16 ? `${t.slice(0, 10)} ${t.slice(11, 16)} UTC` : t
  const isProd = __BUILD_CONTEXT__ === 'production'
  const known = __BUILD_SHA__ !== 'unknown'
  return (
    <footer className="mx-auto max-w-6xl px-4 pb-6 pt-2 text-center text-[11px] text-faint">
      <span className="tnum">
        build{' '}
        {known ? (
          <a
            href={`https://github.com/hazneman/marketalerts/commit/${__BUILD_SHA__}`}
            target="_blank"
            rel="noreferrer"
            className="text-muted hover:text-ink hover:underline"
          >
            {__BUILD_SHA__}
          </a>
        ) : (
          <span className="text-muted">{__BUILD_SHA__}</span>
        )}
        {' · '}
        {when}
        {!isProd && (
          <>
            {' · '}
            <span className="text-accent">{__BUILD_CONTEXT__}</span>
          </>
        )}
      </span>
    </footer>
  )
}

export default function App() {
  const { latest, history, error } = useAlerts()
  // App-level so the sync engine (initial pull + push-on-edit) runs on every
  // tab, not only while Portfolio is mounted. Provided to SyncPanel via context.
  const sync = usePortfolioSync()
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
      <main className="mx-auto max-w-6xl px-4 py-16 text-center text-ink-2">
        <h1 className="mb-3 text-xl font-semibold text-ink">Market Alerts</h1>
        <p>
          No scan data yet ({error}). Run a scan first — locally via{' '}
          <code className="text-accent">./dev.sh</code>, or wait for the daily
          GitHub Action.
        </p>
      </main>
    )
  }
  if (!latest) {
    return <main className="px-4 py-16 text-center text-muted">Loading…</main>
  }

  return (
    <PortfolioSyncContext.Provider value={sync}>
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-hair bg-base/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-2.5">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5">
              <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden="true">
                <rect width="32" height="32" rx="2" className="fill-accent/15" />
                <path
                  d="M5 20l6-7 5 4 5-9 6 8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-accent"
                />
              </svg>
              <h1 className="text-lg font-semibold tracking-tight text-ink">
                Market Alerts
              </h1>
            </div>
            <nav>
              <Tabs
                items={PAGES.map((p) => ({ value: p, label: PAGE_LABELS[p] }))}
                active={page}
                onChange={setPage}
              />
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-muted sm:block">{TAGLINES[page]}</span>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-5">

      {page === 'forex' ? (
        <ForexPage />
      ) : page === 'buys' ? (
        <BuysPage />
      ) : page === 'sectors' ? (
        <SectorsPage />
      ) : page === 'track' ? (
        <TrackRecordPage />
      ) : page === 'portfolio' ? (
        <PortfolioPage />
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
      <BuildStamp />
    </div>
    </PortfolioSyncContext.Provider>
  )
}
