import Badge from './ui/Badge'

export default function DirectionBadge({ direction }: { direction: 'bullish' | 'bearish' }) {
  const bull = direction === 'bullish'
  return (
    <Badge tone={bull ? 'up' : 'down'}>
      <span className={`h-1.5 w-1.5 ${bull ? 'bg-up' : 'bg-down'}`} />
      {bull ? 'Bull' : 'Bear'}
    </Badge>
  )
}
