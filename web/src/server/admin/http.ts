import { ValidationFailedError } from '../errors'
import { assertPermission } from '../permissions'
import { forward } from '../profile/http'
import type { ProfileHttpDeps } from '../profile/http'

export type AdminHttpDeps = ProfileHttpDeps & {
  /** Resolve the caller and refuse unless they are staff who may read the overview. */
  requireStaff?: (headers: Headers) => Promise<{ id: string }>
}

/** The caller, only if their session is active staff with `overview.read`. */
async function staffOnly(headers: Headers): Promise<{ id: string }> {
  const { auth } = await import('#/lib/auth')
  const session = await auth.api.getSession({ headers })
  const staff = await assertPermission(session, 'overview.read')
  return { id: staff.userId }
}

const MAX_DAYS = 365

/** Aggregates over the AI usage ledger for the last `days` days. Staff only; never any text. */
export const handleAiUsage = (request: Request, deps: AdminHttpDeps = {}) => {
  const raw = new URL(request.url).searchParams.get('days')
  const days = raw === null ? 30 : Number(raw)
  return forward(
    request,
    { ...deps, requireUser: deps.requireStaff ?? staffOnly },
    { method: 'GET', path: `/internal/admin/ai-usage?days=${days}` },
    () => {
      if (!Number.isInteger(days) || days < 1 || days > MAX_DAYS) {
        throw new ValidationFailedError()
      }
    },
  )
}
