// Shared class-string constants and the single source of truth for badge tones.
// Every color is a design token (see src/index.css / tailwind.config.js), so
// these theme automatically in light + dark. Import these instead of re-inlining
// the panel / table / input / badge idioms in each component.

// ── Surfaces ────────────────────────────────────────────────────────────────
export const panelCls = 'bg-raised ring-1 ring-hair'
export const tableWrapCls = 'overflow-x-auto bg-raised ring-1 ring-hair'
export const theadCls =
  'bg-overlay text-[10px] font-medium uppercase tracking-wider text-muted'
export const rowCls = 'transition-colors hover:bg-overlay'
export const cellCls = 'px-3 py-1.5'

// ── Inputs & buttons ─────────────────────────────────────────────────────────
export const inputCls =
  'bg-overlay px-2.5 py-1.5 text-sm text-ink placeholder-muted ring-1 ring-hair focus:outline-none focus:ring-accent/50'
export const inputClsSm =
  'bg-overlay px-2 py-1 text-xs text-ink placeholder-muted ring-1 ring-hair focus:outline-none focus:ring-accent/50'
export const btnPrimary =
  'bg-accent/15 px-3 py-1.5 text-sm font-medium text-accent ring-1 ring-accent/30 transition hover:bg-accent/25 disabled:opacity-40'
export const btnGhost =
  'bg-overlay px-3 py-1.5 text-sm text-ink-2 ring-1 ring-hair transition hover:text-ink'

// ── Badge tones — replaces the ~6 duplicated style maps across components ─────
export type Tone = 'up' | 'down' | 'accent' | 'info' | 'de' | 'neutral'

export const badgeRing: Record<Tone, string> = {
  up: 'bg-up/10 text-up ring-1 ring-up/30',
  down: 'bg-down/10 text-down ring-1 ring-down/30',
  accent: 'bg-accent/10 text-accent ring-1 ring-accent/30',
  info: 'bg-info/10 text-info ring-1 ring-info/30',
  de: 'bg-de/10 text-de ring-1 ring-de/30',
  neutral: 'bg-overlay text-muted ring-1 ring-hair',
}

export const badgeFlat: Record<Tone, string> = {
  up: 'bg-up/15 text-up',
  down: 'bg-down/15 text-down',
  accent: 'bg-accent/15 text-accent',
  info: 'bg-info/15 text-info',
  de: 'bg-de/15 text-de',
  neutral: 'bg-overlay text-ink-2',
}
