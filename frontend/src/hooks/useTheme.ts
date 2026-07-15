import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

// Same resolution the FOUC guard in index.html uses: stored choice, else the
// OS preference. Kept in sync so the first React read matches the painted DOM.
function read(): Theme {
  const s = localStorage.getItem('ma-theme')
  if (s === 'light' || s === 'dark') return s
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(read)

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    root.dataset.theme = theme
    localStorage.setItem('ma-theme', theme)
    document
      .querySelector('meta[name=theme-color]')
      ?.setAttribute('content', theme === 'dark' ? '#0a0a0c' : '#f3efe6')
  }, [theme])

  return { theme, toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')) }
}
