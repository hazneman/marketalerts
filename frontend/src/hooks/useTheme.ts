import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const META_COLOR: Record<Theme, string> = { dark: '#0a0a0c', light: '#f3efe6' }

// Same resolution the FOUC guard in index.html uses: stored choice, else the
// OS preference. localStorage can throw (storage blocked / some webviews), so
// it is guarded — a failure falls through to the OS preference instead of
// crashing the render.
function read(): Theme {
  try {
    const s = localStorage.getItem('ma-theme')
    if (s === 'light' || s === 'dark') return s
  } catch {
    /* storage unavailable — use OS preference */
  }
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(read)

  // Apply to the DOM on every change (mount + toggle). Deliberately does NOT
  // persist: writing the OS-derived theme on first mount would pin the site to
  // that value and stop it following later OS changes. We persist only when the
  // user explicitly toggles (below).
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.querySelector('meta[name=theme-color]')?.setAttribute('content', META_COLOR[theme])
  }, [theme])

  const toggle = () =>
    setTheme((t) => {
      const next: Theme = t === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem('ma-theme', next)
      } catch {
        /* storage unavailable — theme still applies for this session */
      }
      return next
    })

  return { theme, toggle }
}
