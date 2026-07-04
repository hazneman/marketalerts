import { useEffect, useState } from 'react'
import type { AlertHistory, ScanResult } from '../types'

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${path}?t=${Date.now()}`)
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`)
  return res.json()
}

export function useAlerts() {
  const [latest, setLatest] = useState<ScanResult | null>(null)
  const [history, setHistory] = useState<AlertHistory | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchJson<ScanResult>('/data/latest.json').then(setLatest).catch((e) => setError(String(e)))
    // history is optional — a brand-new deploy may not have one yet
    fetchJson<AlertHistory>('/data/history.json').then(setHistory).catch(() => setHistory(null))
  }, [])

  return { latest, history, error }
}
