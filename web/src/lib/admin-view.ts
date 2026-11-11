/** Plain formatting for the AI cost and quality page. Nothing here is a score. */

/** USD for people: cents above a cent, fractions of a cent below it, never a bare zero. */
export function usd(value: string | null): string {
  if (value === null) return 'Unknown'
  const n = Number(value)
  if (!Number.isFinite(n)) return 'Unknown'
  if (n === 0) return '$0.00'
  if (n < 0.01) return `$${n.toFixed(4)}`
  return `$${n.toFixed(2)}`
}

export const count = (n: number) => n.toLocaleString('en-US')

/** 1,234 -> "1.2k", 2,500,000 -> "2.5M"; small numbers stay as they are. */
export function tokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 10_000) return `${Math.round(n / 1000)}k`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

const WORKFLOW_NAMES: Record<string, string> = {
  parse: 'Reading a CV',
  screen: 'Screening a job',
  evaluate: 'Fit evaluation',
  tailor: 'Tailoring a CV',
  reach_check: 'Reach check',
  outreach: 'Outreach draft',
}

export const workflowName = (workflow: string) =>
  WORKFLOW_NAMES[workflow] ?? workflow

/** Share of live calls that did not give a usable answer, as a whole percent, or null. */
export function trouble(calls: number, rejected: number, failed: number) {
  if (calls <= 0) return null
  return Math.round(((rejected + failed) / calls) * 100)
}

/** "30 days" or "1 day". */
export const windowLabel = (days: number) =>
  days === 1 ? '1 day' : `${days} days`
