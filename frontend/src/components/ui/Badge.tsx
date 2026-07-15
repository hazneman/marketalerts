import type { ReactNode } from 'react'
import { badgeFlat, badgeRing, type Tone } from '../../lib/ui'

// One badge to replace VERDICT_STYLES / SECTOR_STATE / CONSENSUS_LABELS /
// MARKET_BADGE_STYLES / ALIGNMENT_STYLES / RATING_STYLES / FactorChip / etc.
// `ring` = the outlined state/quality pill; `flat` = the softer verdict/consensus tint.
export default function Badge({
  tone,
  variant = 'ring',
  className = '',
  title,
  children,
}: {
  tone: Tone
  variant?: 'ring' | 'flat'
  className?: string
  title?: string
  children: ReactNode
}) {
  const styles = variant === 'flat' ? badgeFlat[tone] : badgeRing[tone]
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold ${styles} ${className}`}
    >
      {children}
    </span>
  )
}
