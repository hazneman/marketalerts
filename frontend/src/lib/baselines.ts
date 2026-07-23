// Sector-relative judgement of a company-profile metric: green when the value
// is in the better quartile of ITS OWN GICS sector, red when in the worse one,
// neutral in the middle band or when no baseline exists yet (baselines.json
// accumulates nightly; thin sectors publish nothing). Display-only.
import type { BaselinesData, MetricBaseline } from '../types'
import type { Tone } from './ui'

// Which way is "good"? Everything not listed is judged higher-better.
const LOWER_BETTER = new Set([
  'net_debt_to_ebitda', 'debt_to_equity', 'ev_ebitda', 'peg', 'p_fcf', 'payout',
])

export interface MetricJudgement {
  tone: Tone
  title: string
}

export function judgeMetric(
  key: string,
  value: number,
  sector: string | null | undefined,
  baselines: BaselinesData | null,
): MetricJudgement {
  const stats: MetricBaseline | undefined =
    sector && baselines ? baselines.sectors[sector]?.[key] : undefined
  if (!stats) {
    return { tone: 'neutral', title: 'No sector baseline yet — colors appear as nightly coverage builds' }
  }
  const lower = LOWER_BETTER.has(key)
  const good = lower ? value <= stats.p25 : value >= stats.p75
  const bad = lower ? value >= stats.p75 : value <= stats.p25
  const tone: Tone = good ? 'up' : bad ? 'down' : 'neutral'
  const verdict = good ? 'better than ~75% of the sector' : bad ? 'worse than ~75% of the sector' : 'in the sector midrange'
  return {
    tone,
    title: `${sector}: median ${stats.med} · p25 ${stats.p25} / p75 ${stats.p75} (n=${stats.n}) — ${verdict}`,
  }
}
