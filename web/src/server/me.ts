import type { Db } from './db/client'
import { getDb } from './db/client'
import { toResult } from './errors'
import { loadStaff, resolveUser } from './identity'
import type { SessionUser, StaffInfo } from './identity'

export type Me = {
  id: string
  email: string
  displayName: string | null
  locale: string
  timezone: string
  staff: StaffInfo | null
}

export type MeResult =
  { ok: true; me: Me } | { ok: false; code: string; message: string }

/** The `getMe` server function body, kept free of request plumbing so tests can call it. */
export async function buildMe(
  session: { user: SessionUser } | null,
  db: Db = getDb(),
): Promise<MeResult> {
  try {
    const row = await resolveUser(session, db)
    return {
      ok: true,
      me: {
        id: row.id,
        email: row.email,
        displayName: row.displayName,
        locale: row.locale,
        timezone: row.timezone,
        staff: await loadStaff(row.id, db),
      },
    }
  } catch (error) {
    const { code, message } = toResult(error)
    return { ok: false, code, message }
  }
}

/** What the `getMe` server function runs: read the session from the request, then build. */
export async function meFromHeaders(headers: Headers): Promise<MeResult> {
  const { auth } = await import('#/lib/auth')
  return buildMe(await auth.api.getSession({ headers }))
}
