import { sql } from 'drizzle-orm'
import { getDb, getPool } from '#/server/db/client'

/** Remove rows created by a test. Roles and permissions are seed data and stay. */
export async function resetData() {
  const db = getDb()
  // audit_log is append-only; the trigger is dropped for cleanup and restored.
  await db.execute(
    sql`alter table audit_log disable trigger audit_log_no_change`,
  )
  await db.execute(sql`delete from audit_log`)
  await db.execute(
    sql`alter table audit_log enable trigger audit_log_no_change`,
  )
  await db.execute(sql`delete from staff_member`)
  await db.execute(sql`delete from "user"`)
  await db.execute(sql`delete from auth_user`)
}

export async function closeDb() {
  await getPool().end()
}
