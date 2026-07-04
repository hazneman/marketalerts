import type { HistoryDay } from '../types'

export type DirectionFilter = 'all' | 'bullish' | 'bearish'

interface Props {
  search: string
  onSearch: (v: string) => void
  direction: DirectionFilter
  onDirection: (v: DirectionFilter) => void
  days: HistoryDay[]
  selectedDay: string
  onDay: (v: string) => void
}

export default function FilterBar({
  search, onSearch, direction, onDirection, days, selectedDay, onDay,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="Search ticker…"
        className="w-44 rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
      />
      <div className="flex overflow-hidden rounded-md border border-slate-700 text-sm">
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
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
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
