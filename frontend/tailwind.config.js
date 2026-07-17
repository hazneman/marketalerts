/** @type {import('tailwindcss').Config} */

// Every token is an "R G B" triplet CSS variable (see src/index.css); wrapping
// it in rgb(var(--x) / <alpha-value>) keeps all `/opacity` utilities working.
const token = (name) => `rgb(var(${name}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono Variable"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        base: token('--bg-base'),
        raised: token('--bg-raised'),
        overlay: token('--bg-overlay'),
        inset: token('--bg-inset'),
        hair: token('--border'),
        'hair-strong': token('--border-strong'),
        ink: token('--text-primary'),
        'ink-2': token('--text-secondary'),
        muted: token('--text-muted'),
        faint: token('--text-faint'),
        accent: token('--accent'),
        up: token('--up'),
        down: token('--down'),
        info: token('--info'),
        de: token('--de'),
      },
      // Pro Terminal: sharp edges. Existing rounded-* classes emit 1–3px so no
      // per-file churn; dots/markers become tiny on-brand "LED" squares.
      borderRadius: {
        none: '0',
        sm: '1px',
        DEFAULT: '2px',
        md: '2px',
        lg: '2px',
        xl: '2px',
        '2xl': '3px',
        '3xl': '3px',
        full: '2px',
      },
    },
  },
  plugins: [],
}
