import { eq, sql } from 'drizzle-orm'
import { getDb } from './db/client'
import type { Db } from './db/client'
import { role, rolePermission, staffMember, user } from './db/schema'
import {
  ConflictError,
  PermissionDeniedError,
  UnauthorizedError,
} from './errors'

export type SessionUser = { id: string; email: string; name: string }
export type AppUser = typeof user.$inferSelect
export type StaffInfo = { role: string; permissions: string[] }

/**
 * Map a verified Better Auth session user to the app `user` row, creating it on
 * first use. Concurrent first requests create one row.
 */
export async function resolveUser(
  session: { user: SessionUser } | null,
  db: Db = getDb(),
): Promise<AppUser> {
  if (!session) throw new UnauthorizedError()
  const email = session.user.email.trim().toLowerCase()
  if (!email)
    throw new UnauthorizedError('Your session is not valid. Sign in again.')

  await db
    .insert(user)
    .values({
      authSubject: session.user.id,
      email,
      displayName: session.user.name.trim() || null,
    })
    .onConflictDoNothing()

  const rows: AppUser[] = await db
    .select()
    .from(user)
    .where(eq(user.authSubject, session.user.id))
  const row = rows.at(0)
  if (!row) {
    // The insert was skipped by the email unique constraint: another identity owns it.
    throw new ConflictError('An account with this email already exists.')
  }
  if (row.status !== 'active')
    throw new PermissionDeniedError('This account is not active.')
  return row
}

export async function requireUser(headers: Headers): Promise<AppUser> {
  const { auth } = await import('#/lib/auth')
  return resolveUser(await auth.api.getSession({ headers }))
}

export async function loadStaff(
  userId: string,
  db: Db = getDb(),
): Promise<StaffInfo | null> {
  const members = await db
    .select({ roleId: staffMember.roleId, role: role.name })
    .from(staffMember)
    .innerJoin(role, eq(role.id, staffMember.roleId))
    .where(eq(staffMember.userId, userId))
  const member = members.at(0)
  if (!member) return null
  const rows = await db
    .select({ permission: rolePermission.permission })
    .from(rolePermission)
    .where(eq(rolePermission.roleId, member.roleId))
    .orderBy(sql`${rolePermission.permission}`)
  return { role: member.role, permissions: rows.map((r) => r.permission) }
}
