import { execSync } from 'node:child_process'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Build stamp shown in the site footer so you can tell at a glance whether the
// deployed site matches your latest commit. On Netlify these come from the
// build environment; locally we fall back to git so `npm run dev`/`build` still
// show something meaningful.
function gitShort(): string {
  try {
    return execSync('git rev-parse --short HEAD').toString().trim()
  } catch {
    return 'unknown'
  }
}

const sha = (process.env.COMMIT_REF || gitShort()).slice(0, 7)
const context = process.env.CONTEXT || 'local'
const buildTime = new Date().toISOString()

export default defineConfig({
  plugins: [react()],
  server: { port: 3100 },
  define: {
    __BUILD_SHA__: JSON.stringify(sha),
    __BUILD_TIME__: JSON.stringify(buildTime),
    __BUILD_CONTEXT__: JSON.stringify(context),
  },
})
