import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import {
  adoptStore, loadPortfolio, localUpdatedAt, subscribe, type PortfolioStore,
} from '../lib/portfolio'
import {
  clearSyncCode, CODE_RE, generateSyncCode, getSyncCode, isEmpty, pull, push, pushBeacon,
  setSyncCode,
} from '../lib/sync'

export type SyncStatus = 'off' | 'syncing' | 'synced' | 'error'

export interface PortfolioSync {
  code: string | null
  status: SyncStatus
  lastSyncedAt: string | null
  error: string | null
  enable: () => Promise<void>
  connect: (code: string) => Promise<void>
  disconnect: () => void
  syncNow: () => Promise<void>
}

const PUSH_DEBOUNCE_MS = 1500

// One-owner-many-devices sync: last-write-wins by `updated_at`. Adopting a
// remote copy writes localStorage, which fires the change event we also listen
// to for pushing — a `suppress` ref breaks that loop so an adopt never bounces
// straight back up as a push.
export function usePortfolioSync(): PortfolioSync {
  const [code, setCode] = useState<string | null>(() => getSyncCode())
  const [status, setStatus] = useState<SyncStatus>(() => (getSyncCode() ? 'syncing' : 'off'))
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const suppress = useRef(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const codeRef = useRef<string | null>(getSyncCode())
  codeRef.current = code

  // Adopt a remote copy while suppressing the change-event → push loop. The
  // reset MUST run even if adoptStore throws (quota / private mode), else the
  // suppress ref sticks true and no edit ever syncs again for the session.
  const adoptSuppressed = useCallback((store: PortfolioStore, at: string) => {
    suppress.current = true
    try {
      adoptStore(store, at)
    } finally {
      suppress.current = false
    }
  }, [])

  const doPush = useCallback(async (c: string) => {
    setStatus('syncing')
    setError(null)
    try {
      const at = localUpdatedAt() || new Date().toISOString()
      await push(c, loadPortfolio(), at)
      setLastSyncedAt(at)
      setStatus('synced')
    } catch {
      setStatus('error')
      setError('Could not reach the sync service — your data is safe locally.')
    }
  }, [])

  // Pull remote and reconcile against local by timestamp. Returns nothing;
  // updates status. Adopts remote if it is newer, else pushes local up.
  const reconcile = useCallback(async (c: string) => {
    setStatus('syncing')
    setError(null)
    try {
      const remote = await pull(c)
      const localAt = localUpdatedAt()
      if (remote.store && remote.updated_at && (!localAt || remote.updated_at > localAt)) {
        adoptSuppressed(remote.store, remote.updated_at)
        setLastSyncedAt(remote.updated_at)
        setStatus('synced')
      } else {
        const at = localAt || new Date().toISOString()
        await push(c, loadPortfolio(), at)
        if (!localAt) adoptSuppressed(loadPortfolio(), at) // stamp so we don't re-push endlessly
        setLastSyncedAt(at)
        setStatus('synced')
      }
    } catch {
      setStatus('error')
      setError('Could not reach the sync service — your data is safe locally.')
    }
  }, [])

  // Initial reconcile when a code is already saved (page load / new device).
  useEffect(() => {
    const saved = getSyncCode()
    if (saved) reconcile(saved)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Push local edits up (debounced), unless the edit came from an adopt.
  useEffect(() => {
    const unsub = subscribe(() => {
      if (suppress.current) return
      const c = codeRef.current
      if (!c) return
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => doPush(c), PUSH_DEBOUNCE_MS)
    })
    return () => {
      unsub()
      if (timer.current) clearTimeout(timer.current) // no push firing after unmount
    }
  }, [doPush])

  // If the page is hidden/closing with a push still pending in the debounce
  // window, flush it via sendBeacon so a last-second edit isn't lost.
  useEffect(() => {
    const flush = () => {
      if (!timer.current) return
      clearTimeout(timer.current)
      timer.current = null
      const c = codeRef.current
      if (!c) return
      pushBeacon(c, loadPortfolio(), localUpdatedAt() || new Date().toISOString())
    }
    const onVis = () => {
      if (document.visibilityState === 'hidden') flush()
    }
    window.addEventListener('pagehide', flush)
    document.addEventListener('visibilitychange', onVis)
    return () => {
      window.removeEventListener('pagehide', flush)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [])

  const enable = useCallback(async () => {
    const c = generateSyncCode()
    setSyncCode(c)
    setCode(c)
    await reconcile(c) // remote is empty → seeds the cloud from this device
  }, [reconcile])

  const connect = useCallback(async (input: string) => {
    const c = input.trim().toLowerCase()
    if (!CODE_RE.test(c)) {
      setStatus('error')
      setError('That code looks wrong — expected 8–64 letters and digits.')
      return
    }
    setStatus('syncing')
    setError(null)
    try {
      const remote = await pull(c)
      const local = loadPortfolio()
      if (!isEmpty(remote.store) && !isEmpty(local)) {
        const useCloud = window.confirm(
          `This device has ${local.positions.length} open / ${local.closed.length} closed positions.\n` +
            `The code's cloud copy has ${remote.store!.positions.length} open / ` +
            `${remote.store!.closed.length} closed.\n\n` +
            `OK  = load the cloud copy (replaces this device's data)\n` +
            `Cancel = keep this device and overwrite the cloud`,
        )
        if (useCloud) {
          adoptSuppressed(remote.store!, remote.updated_at || new Date().toISOString())
          setLastSyncedAt(remote.updated_at)
        } else {
          const at = new Date().toISOString()
          await push(c, local, at)
          adoptSuppressed(local, at)
          setLastSyncedAt(at)
        }
      } else if (!isEmpty(remote.store)) {
        adoptSuppressed(remote.store!, remote.updated_at || new Date().toISOString())
        setLastSyncedAt(remote.updated_at)
      } else {
        const at = localUpdatedAt() || new Date().toISOString()
        await push(c, local, at)
        setLastSyncedAt(at)
      }
      setSyncCode(c)
      setCode(c)
      setStatus('synced')
    } catch {
      setStatus('error')
      setError('Could not reach the sync service — check the code and your connection.')
    }
  }, [])

  const disconnect = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    clearSyncCode()
    setCode(null)
    setStatus('off')
    setError(null)
    setLastSyncedAt(null)
  }, [])

  const syncNow = useCallback(async () => {
    const c = codeRef.current
    if (c) await reconcile(c)
  }, [reconcile])

  return { code, status, lastSyncedAt, error, enable, connect, disconnect, syncNow }
}

// The sync engine must run app-wide, not only while the Portfolio tab is
// mounted — otherwise a "+ portfolio" add from the Buys/Stocks tab is saved
// locally but never pushed. App calls usePortfolioSync() once and provides it
// here; SyncPanel consumes it via usePortfolioSyncCtx().
export const PortfolioSyncContext = createContext<PortfolioSync | null>(null)

export function usePortfolioSyncCtx(): PortfolioSync {
  const ctx = useContext(PortfolioSyncContext)
  if (!ctx) throw new Error('usePortfolioSyncCtx must be used within PortfolioSyncContext')
  return ctx
}
