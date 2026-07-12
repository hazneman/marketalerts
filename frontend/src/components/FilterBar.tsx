import { MARKET_LABELS, type HistoryDay } from '../types'

export type DirectionFilter = 'all' | 'bullish' | 'bearish'

interface Props {
  search: string
  onSearch: (v: string) => void
  direction: DirectionFilter
  onDirection: (v: DirectionFilter) => void
  days: HistoryDay[]
  selectedDay: string
  onDay: (v: string) => void
  markets: string[]
  market: string
  onMarket: (v: string) => void
}

export default function FilterBar({
  search, onSearch, direction, onDirection, days, selectedDay, onDay,
  markets, market, onMarket,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="Search ticker…"
        className="w-44 rounded-lg bg-white/[0.04] px-3 py-1.5 text-sm text-slate-100 placeholder-slate-500 ring-1 ring-white/10 transition focus:bg-white/[0.06] focus:outline-none focus:ring-sky-400/40"
      />
      {markets.length > 1 && (
        <div className="flex rounded-full bg-white/5 p-1 text-sm ring-1 ring-white/10">
          {['all', ...markets].map((m) => (
            <button
              key={m}
              onClick={() => onMarket(m)}
              className={`rounded-full px-3 py-1 transition-colors ${
                market === m
                  ? 'bg-sky-500/20 font-medium text-sky-300 ring-1 ring-sky-400/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {m === 'all' ? 'All markets' : MARKET_LABELS[m] ?? m.toUpperCase()}
            </button>
          ))}
        </div>
      )}
      <div className="flex rounded-full bg-white/5 p-1 text-sm ring-1 ring-white/10">
        {(['all', 'bullish', 'bearish'] as const).map((d) => (
          <button
            key={d}
            onClick={() => onDirection(d)}
            className={`px-3 py-1.5 capitalize ${
              direction === d
                ? d === 'bearish'
                  ? 'bg-rose-500/20 text-rose-300'
                  : d === 'bullish'
                    ? 'bg-emerald-500/20 text-emerald-300'
                    : 'bg-sky-500/20 text-sky-300'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            {d}
          </button>
        ))}
      </div>
      {days.length > 1 && (
        <select
          value={selectedDay}
          onChange={(e) => onDay(e.target.value)}
          className="rounded-lg bg-white/[0.04] px-3 py-1.5 text-sm text-slate-100 ring-1 ring-white/10 focus:outline-none focus:ring-sky-400/40"
        >
          {days.map((d) => (
            <option key={d.bar_date} value={d.bar_date}>
              {d.bar_date} ({d.alerts.length} alerts)
            </option>
          ))}
        </select>
      )}
    </div>
  )
}
