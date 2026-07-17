import type { ReactNode } from 'react'

// The amber "tick + title" heading used atop every page. `right` is optional
// trailing content (counts, subtitles, controls).
export default function SectionHeading({
  title,
  right,
}: {
  title: ReactNode
  right?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight text-ink">
        <span className="h-4 w-1 bg-accent" />
        {title}
      </h2>
      {right}
    </div>
  )
}
