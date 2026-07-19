// Portfolio store — positions and closed trades live in the browser's
// localStorage (this is a static site: your holdings never leave your
// machine). Export/import gives a JSON backup for moving browsers.

export interface Position {
  id: string
  ticker: string
  market?: string
  shares: number
  avg_cost: number
  date: string // YYYY-MM-DD buy date
  added_from?: string // rule that triggered the buy, for the backlog story
  target_mean?: number // analyst mean target captured at add time (Buy-card adds)
  target_as_of?: string // date the target was captured — targets go stale
}

export interface ClosedTrade extends Position {
  sell_price: number
  sell_date: string
}

export interface PortfolioStore {
  positions: Position[]
  closed: ClosedTrade[]
}

const KEY = 'market-alerts-portfolio-v1'
const EVENT = 'portfolio-changed'

export function loadPortfolio(): PortfolioStore {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return { positions: [], closed: [] }
    const parsed = JSON.parse(raw)
    return {
      positions: Array.isArray(parsed.positions) ? parsed.positions : [],
      closed: Array.isArray(parsed.closed) ? parsed.closed : [],
    }
  } catch {
    return { positions: [], closed: [] }
  }
}

function save(store: PortfolioStore) {
  localStorage.setItem(KEY, JSON.stringify(store))
  window.dispatchEvent(new CustomEvent(EVENT))
}

export function subscribe(cb: () => void): () => void {
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) cb()
  }
  window.addEventListener(EVENT, cb)
  window.addEventListener('storage', onStorage)
  return () => {
    window.removeEventListener(EVENT, cb)
    window.removeEventListener('storage', onStorage)
  }
}

export function addPosition(p: Omit<Position, 'id'>): void {
  const store = loadPortfolio()
  store.positions.push({ ...p, id: crypto.randomUUID() })
  save(store)
}

export function updatePosition(id: string, patch: Partial<Omit<Position, 'id'>>): void {
  const store = loadPortfolio()
  const pos = store.positions.find((p) => p.id === id)
  if (!pos) return
  Object.assign(pos, patch)
  save(store)
}

export function deletePosition(id: string): void {
  const store = loadPortfolio()
  store.positions = store.positions.filter((p) => p.id !== id)
  save(store)
}

export function closePosition(id: string, sell_price: number, sell_date: string): void {
  const store = loadPortfolio()
  const pos = store.positions.find((p) => p.id === id)
  if (!pos) return
  store.positions = store.positions.filter((p) => p.id !== id)
  store.closed.unshift({ ...pos, sell_price, sell_date })
  save(store)
}

export function deleteClosed(id: string): void {
  const store = loadPortfolio()
  store.closed = store.closed.filter((p) => p.id !== id)
  save(store)
}

export function exportPortfolio(): string {
  return JSON.stringify(loadPortfolio(), null, 1)
}

export function importPortfolio(json: string): boolean {
  try {
    const parsed = JSON.parse(json)
    if (!Array.isArray(parsed.positions) || !Array.isArray(parsed.closed)) return false
    save({ positions: parsed.positions, closed: parsed.closed })
    return true
  } catch {
    return false
  }
}

export function hasTicker(ticker: string): boolean {
  return loadPortfolio().positions.some((p) => p.ticker === ticker)
}
