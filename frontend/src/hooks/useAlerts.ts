import { useEffect, useState } from 'react'
import { loadPortfolio, subscribe, type PortfolioStore } from '../lib/portfolio'
import type { AlertHistory, ForexData, PricesData, ScanResult, SectorData } from '../types'

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

export function useForex() {
  const [forex, setForex] = useState<ForexData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchJson<ForexData>('/data/forex.json').then(setForex).catch((e) => setError(String(e)))
  }, [])

  return { forex, error }
}

export function useSectors() {
  const [sectors, setSectors] = useState<SectorData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchJson<SectorData>('/data/sectors.json').then(setSectors).catch((e) => setError(String(e)))
  }, [])

  return { sectors, error }
}

export function usePrices() {
  const [prices, setPrices] = useState<PricesData | null>(null)

  useEffect(() => {
    fetchJson<PricesData>('/data/prices.json').then(setPrices).catch(() => setPrices(null))
  }, [])

  return prices
}

export function usePortfolio(): PortfolioStore {
  const [store, setStore] = useState<PortfolioStore>(() => loadPortfolio())

  useEffect(() => subscribe(() => setStore(loadPortfolio())), [])

  return store
}
