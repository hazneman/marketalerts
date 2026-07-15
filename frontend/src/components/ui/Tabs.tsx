import type { Tone } from '../../lib/ui'

export interface TabItem<T extends string> {
  value: T
  label: string
  tone?: Tone // active-state color; defaults to accent (amber)
}

// Literal class strings (not interpolated) so Tailwind's JIT emits them.
const ACTIVE: Record<Tone, string> = {
  up: 'text-up border-up',
  down: 'text-down border-down',
  accent: 'text-accent border-accent',
  info: 'text-info border-info',
  de: 'text-de border-de',
  neutral: 'text-ink border-ink',
}

// Squared, underline-style segmented control — the terminal replacement for the
// old rounded pill nav. Used by the app nav and the Stocks filter groups.
export default function Tabs<T extends string>({
  items,
  active,
  onChange,
  size = 'md',
}: {
  items: TabItem<T>[]
  active: T
  onChange: (v: T) => void
  size?: 'sm' | 'md'
}) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm'
  return (
    <div className="flex bg-overlay ring-1 ring-hair">
      {items.map((it) => {
        const on = active === it.value
        const tone = it.tone ?? 'accent'
        return (
          <button
            key={it.value}
            onClick={() => onChange(it.value)}
            className={`-mb-px border-b-2 capitalize transition-colors ${pad} ${
              on
                ? `bg-base font-medium ${ACTIVE[tone]}`
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {it.label}
          </button>
        )
      })}
    </div>
  )
}
