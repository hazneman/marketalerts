export default function DirectionBadge({ direction }: { direction: 'bullish' | 'bearish' }) {
  const bull = direction === 'bullish'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${
        bull
          ? 'bg-emerald-500/10 text-emerald-300 ring-emerald-400/20'
          : 'bg-rose-500/10 text-rose-300 ring-rose-400/20'
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${bull ? 'bg-emerald-400' : 'bg-rose-400'}`}
      />
      {bull ? 'Bull' : 'Bear'}
    </span>
  )
}
