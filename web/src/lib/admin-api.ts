import type { Result } from './profile-api'

type Deps = { fetchFn?: typeof fetch }

const SAFE_CODE = /^[a-z][a-z_]{0,49}$/

/** Money arrives as decimal strings; counts and tokens as numbers. No text, no user ids. */
export type UsageWorkflow = {
  workflow: string
  calls: number
  cacheHits: number
  rejected: number
  failed: number
  tokensIn: number
  tokensOut: number
  costUsd: string
  unknownCostCalls: number
  avgCostUsd: string | null
}

export type UsageRow = {
  workflow: string
  provider: string
  model: string
  promptVersion: string
  calls: number
  cacheHits: number
  rejected: number
  failed: number
  tokensIn: number
  tokensOut: number
  costUsd: string
  unknownCostCalls: number
  avgCostUsd: string | null
  cacheSavingsUsd: string
}

export type UsageReport = {
  days: number
  since: string
  workflows: UsageWorkflow[]
  rows: UsageRow[]
  totalCostUsd: string
  unknownCostCalls: number
  cacheSavingsUsd: string
  compare: { label: string; configured: boolean; estimateUsd: string | null }
  /** Null until the golden set exists (feature 8d). */
  goldenSet: null
}

/** The AI usage report for staff. A non-staff caller gets `forbidden`. */
export async function getAiUsage(
  days = 30,
  deps: Deps = {},
): Promise<Result<UsageReport>> {
  const fetchFn = deps.fetchFn ?? fetch
  let response: Response
  try {
    response = await fetchFn(
      `/api/admin/ai-usage?days=${encodeURIComponent(String(days))}`,
      { method: 'GET', credentials: 'same-origin' },
    )
  } catch {
    return { ok: false, code: 'network', message: 'Network error.' }
  }
  let body: unknown
  try {
    body = await response.json()
  } catch {
    return { ok: false, code: 'unexpected', message: 'Unexpected response.' }
  }
  if (response.ok) return { ok: true, data: body as UsageReport }
  const raw = (body as { code?: unknown } | null)?.code
  const code =
    typeof raw === 'string' && SAFE_CODE.test(raw) ? raw : 'unexpected'
  return { ok: false, code, message: 'Request failed.' }
}
