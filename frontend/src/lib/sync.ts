// Cross-device portfolio sync client. Talks to the `sync` Netlify function,
// which stores one JSON blob per private "sync code" in Netlify Blobs. The code
// is a bearer secret kept in this browser's localStorage; enter it on another
// device to pull the same portfolio. Reconciliation is last-write-wins by the
// `updated_at` timestamp — fine for a single owner across a few devices.
import type { PortfolioStore } from './portfolio'

const CODE_KEY = 'market-alerts-sync-code-v1'
const ENDPOINT = '/.netlify/functions/sync'

export const CODE_RE = /^[a-z0-9]{8,64}$/i

export function getSyncCode(): string | null {
  try {
    return localStorage.getItem(CODE_KEY)
  } catch {
    return null
  }
}

export function setSyncCode(code: string): void {
  try {
    localStorage.setItem(CODE_KEY, code)
  } catch {
    /* private mode / storage full — sync just won't persist the code */
  }
}

export function clearSyncCode(): void {
  try {
    localStorage.removeItem(CODE_KEY)
  } catch {
    /* ignore */
  }
}

// 24 chars of [0-9a-z] from the CSPRNG — unguessable, easy to copy/paste.
export function generateSyncCode(): string {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => b.toString(36).padStart(2, '0')).join('').slice(0, 24)
}

export interface RemoteState {
  store: PortfolioStore | null
  updated_at: string | null
}

export async function pull(code: string): Promise<RemoteState> {
  const r = await fetch(`${ENDPOINT}?code=${encodeURIComponent(code)}`, { cache: 'no-store' })
  if (!r.ok) throw new Error(`sync pull failed (${r.status})`)
  const j = (await r.json()) as RemoteState
  return { store: j.store ?? null, updated_at: j.updated_at ?? null }
}

export async function push(
  code: string,
  store: PortfolioStore,
  updated_at: string,
): Promise<void> {
  const r = await fetch(`${ENDPOINT}?code=${encodeURIComponent(code)}`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ store, updated_at }),
  })
  if (!r.ok) throw new Error(`sync push failed (${r.status})`)
}

export function isEmpty(store: PortfolioStore | null | undefined): boolean {
  return !store || store.positions.length + store.closed.length === 0
}
