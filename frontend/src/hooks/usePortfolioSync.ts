import { useCallback, useEffect, useRef, useState } from 'react'
import { adoptStore, loadPortfolio, localUpdatedAt, subscribe } from '../lib/portfolio'
import {
  clearSyncCode, CODE_RE, generateSyncCode, getSyncCode, isEmpty, pull, push, setSyncCode,
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
        suppress.current = true
        adoptStore(remote.store, remote.updated_at)
        suppress.current = false
        setLastSyncedAt(remote.updated_at)
        setStatus('synced')
      } else {
        const at = localAt || new Date().toISOString()
        await push(c, loadPortfolio(), at)
        if (!localAt) {
          suppress.current = true
          adoptStore(loadPortfolio(), at) // stamp so we don't re-push endlessly
          suppress.current = false
        }
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
    return subscribe(() => {
      if (suppress.current) return
      const c = codeRef.current
      if (!c) return
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => doPush(c), PUSH_DEBOUNCE_MS)
    })
  }, [doPush])

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
          suppress.current = true
          adoptStore(remote.store!, remote.updated_at || new Date().toISOString())
          suppress.current = false
          setLastSyncedAt(remote.updated_at)
        } else {
          const at = new Date().toISOString()
          await push(c, local, at)
          suppress.current = true
          adoptStore(local, at)
          suppress.current = false
          setLastSyncedAt(at)
        }
      } else if (!isEmpty(remote.store)) {
        suppress.current = true
        adoptStore(remote.store!, remote.updated_at || new Date().toISOString())
        suppress.current = false
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
