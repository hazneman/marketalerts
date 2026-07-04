export default function DirectionBadge({ direction }: { direction: 'bullish' | 'bearish' }) {
  const bull = direction === 'bullish'
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        bull ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
      }`}
    >
      {bull ? '▲' : '▼'} {bull ? 'Bull' : 'Bear'}
    </span>
  )
}
