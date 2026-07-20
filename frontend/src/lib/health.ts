// Position health scoring — turns the daily health.json snapshot into a
// caution level for a stock you HOLD.
//
// Deliberately a CAUTION indicator, not an exit signal: docs/EXITS.md tested
// six exit rules and only the RSI>75 trim beat buy-and-hold in both windows —
// stop-loss and SMA-exit rules underperformed simply holding. So this surfaces
// deterioration for a human to judge; it never says "sell".
import type { TickerHealth } from '../types'

export type HealthLevel = 'strong' | 'ok' | 'caution' | 'weak'

export interface HealthReason {
  text: string
  severity: 1 | 2 // 1 = caution, 2 = serious
}

export interface HealthVerdict {
  level: HealthLevel
  label: string
  reasons: HealthReason[]
  positives: string[]
}

const RSI_TRIM = 75          // the one backtest-validated exit hint
const NEAR_SMA_PCT = 2       // "hovering at the line"
const DRAWDOWN_CAUTION = -15 // % off the 1-year peak

/** Grade a held position. `drawdownSinceEntry` is optional (computed client-side
 *  from entry price vs the ticker's recent peak). */
export function assessHealth(h: TickerHealth | undefined): HealthVerdict {
  if (!h) {
    return { level: 'ok', label: 'No data', reasons: [], positives: [] }
  }
  const reasons: HealthReason[] = []
  const positives: string[] = []

  // --- trend: where price sits vs its 200-day line -------------------------
  if (h.vs_sma200_pct !== undefined) {
    if (h.vs_sma200_pct < 0) {
      reasons.push({ text: `Below its 200-day average (${h.vs_sma200_pct.toFixed(1)}%)`, severity: 2 })
    } else if (h.vs_sma200_pct < NEAR_SMA_PCT) {
      reasons.push({ text: `Hovering just above its 200-day average (+${h.vs_sma200_pct.toFixed(1)}%)`, severity: 1 })
    } else {
      positives.push(`Comfortably above its 200-day average (+${h.vs_sma200_pct.toFixed(1)}%)`)
    }
  }
  if (h.vs_sma50_pct !== undefined && h.vs_sma50_pct < 0 && (h.vs_sma200_pct ?? 1) >= 0) {
    // lost the shorter trend while the long one still holds = early warning
    reasons.push({ text: `Lost its 50-day average (${h.vs_sma50_pct.toFixed(1)}%)`, severity: 1 })
  }

  // --- momentum ------------------------------------------------------------
  if (h.macd_bullish === false) {
    reasons.push({ text: 'MACD momentum has turned negative', severity: 1 })
  } else if (h.macd_bullish) {
    positives.push('MACD momentum positive')
  }
  if (h.chg_20d_pct !== undefined && h.chg_20d_pct < -10) {
    reasons.push({ text: `Down ${h.chg_20d_pct.toFixed(1)}% over the last month`, severity: 1 })
  }

  // --- drawdown ------------------------------------------------------------
  if (h.drawdown_pct !== undefined && h.drawdown_pct <= DRAWDOWN_CAUTION) {
    reasons.push({
      text: `${Math.abs(h.drawdown_pct).toFixed(0)}% below its 1-year peak`,
      severity: h.drawdown_pct <= -25 ? 2 : 1,
    })
  }

  // --- overbought: the ONLY exit rule that survived backtesting -------------
  if (h.rsi !== undefined && h.rsi > RSI_TRIM) {
    reasons.push({
      text: `RSI ${h.rsi.toFixed(0)} — overbought; the one exit rule backtests supported (trim, not exit)`,
      severity: 1,
    })
  }

  // --- context -------------------------------------------------------------
  if (h.sector_state === 'lagging') {
    reasons.push({ text: 'Its sector is lagging the market', severity: 1 })
  } else if (h.sector_state === 'leading') {
    positives.push('Sector is leading the market')
  }

  // --- recent alerts (30-day memory, so a missed day still shows) -----------
  for (const w of h.recent_warnings ?? []) {
    const isTrim = w.category === 'rsi_extended'
    reasons.push({
      text: `${isTrim ? 'Take-profit (RSI>75) alert' : 'Bearish signal'} fired on ${w.date}`,
      severity: isTrim ? 1 : 2,
    })
  }

  const serious = reasons.filter((r) => r.severity === 2).length
  const level: HealthLevel =
    serious >= 2 ? 'weak'
      : serious === 1 ? 'caution'
        : reasons.length >= 2 ? 'caution'
          : reasons.length === 1 ? 'ok'
            : 'strong'
  const label =
    level === 'weak' ? 'Weak' : level === 'caution' ? 'Caution' : level === 'ok' ? 'OK' : 'Strong'
  return { level, label, reasons, positives }
}

export const HEALTH_DOT: Record<HealthLevel, string> = {
  strong: '●',
  ok: '●',
  caution: '▲',
  weak: '▼',
}
