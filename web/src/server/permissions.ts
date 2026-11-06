import { getDb } from './db/client'
import type { Db } from './db/client'
import { PermissionDeniedError } from './errors'
import { loadStaff, resolveUser } from './identity'
import type { SessionUser } from './identity'

export const PERMISSIONS = [
  'overview.read',
  'users.read',
  'users.write',
  'billing.read',
  'billing.refund',
  'pricing.write',
  'tickets.read',
  'tickets.reply',
  'jobs.write',
  'ai.write',
  'flags.write',
  'ops.write',
  'audit.read',
] as const

export type Permission = (typeof PERMISSIONS)[number]

/** Must equal the rows the baseline migration seeds into `role_permission`. */
export const ROLE_PERMISSIONS: Record<string, readonly Permission[]> = {
  support: ['overview.read', 'users.read', 'tickets.read', 'tickets.reply'],
  finance: [
    'overview.read',
    'users.read',
    'billing.read',
    'billing.refund',
    'pricing.write',
  ],
  admin: PERMISSIONS.filter(
    (p) => p !== 'billing.refund' && p !== 'pricing.write',
  ),
  owner: PERMISSIONS,
}

export type StaffContext = {
  userId: string
  role: string
  permissions: string[]
}

/** Refuse unless the session's user is active staff whose role has `permission`. */
export async function assertPermission(
  session: { user: SessionUser } | null,
  permission: Permission,
  db: Db = getDb(),
): Promise<StaffContext> {
  const user = await resolveUser(session, db) // also refuses suspended or deleted users
  const staff = await loadStaff(user.id, db)
  if (!staff || !staff.permissions.includes(permission)) {
    throw new PermissionDeniedError()
  }
  return { userId: user.id, ...staff }
}

export async function requirePermission(
  headers: Headers,
  permission: Permission,
): Promise<StaffContext> {
  const { auth } = await import('#/lib/auth')
  return assertPermission(await auth.api.getSession({ headers }), permission)
}
