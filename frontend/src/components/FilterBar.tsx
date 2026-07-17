import { MARKET_LABELS, type HistoryDay } from '../types'
import { inputCls } from '../lib/ui'
import Tabs, { type TabItem } from './ui/Tabs'

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

const DIRECTION_ITEMS: TabItem<DirectionFilter>[] = [
  { value: 'all', label: 'All', tone: 'info' },
  { value: 'bullish', label: 'Bullish', tone: 'up' },
  { value: 'bearish', label: 'Bearish', tone: 'down' },
]

export default function FilterBar({
  search, onSearch, direction, onDirection, days, selectedDay, onDay,
  markets, market, onMarket,
}: Props) {
  const marketItems: TabItem<string>[] = ['all', ...markets].map((m) => ({
    value: m,
    label: m === 'all' ? 'All markets' : MARKET_LABELS[m] ?? m.toUpperCase(),
    tone: 'info',
  }))
  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="Search ticker…"
        className={`w-44 ${inputCls}`}
      />
      {markets.length > 1 && (
        <Tabs items={marketItems} active={market} onChange={onMarket} size="sm" />
      )}
      <Tabs items={DIRECTION_ITEMS} active={direction} onChange={onDirection} size="sm" />
      {days.length > 1 && (
        <select
          value={selectedDay}
          onChange={(e) => onDay(e.target.value)}
          className={inputCls}
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
