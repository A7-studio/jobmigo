import { sql } from 'drizzle-orm'
import { afterAll, beforeEach, describe, expect, it } from 'vitest'
import { AuditReasonRequiredError, recordAudit } from '#/server/audit'
import { getDb } from '#/server/db/client'
import { PermissionDeniedError } from '#/server/errors'
import { resolveUser } from '#/server/identity'
import { ROLE_PERMISSIONS, assertPermission } from '#/server/permissions'
import { closeDb, resetData } from './helpers'

const db = getDb()
const session = (id: string, email: string) => ({
  user: { id, email, name: id },
})

async function makeStaff(id: string, roleName: string) {
  const row = await resolveUser(session(id, `${id}@example.com`), db)
  await db.execute(
    sql`insert into staff_member (user_id, role_id)
        select ${row.id}, id from role where name = ${roleName}`,
  )
  return row
}

beforeEach(resetData)
afterAll(closeDb)

describe('permissions', () => {
  it('matches the seeded role_permission rows', async () => {
    for (const [name, perms] of Object.entries(ROLE_PERMISSIONS)) {
      const rows = await db.execute(
        sql`select p.permission from role_permission p join role r on r.id = p.role_id
            where r.name = ${name} order by p.permission`,
      )
      expect(rows.rows.map((r) => r.permission)).toEqual([...perms].sort())
    }
  })

  it('refuses a user who is not staff', async () => {
    await resolveUser(session('plain', 'plain@example.com'), db)
    await expect(
      assertPermission(session('plain', 'plain@example.com'), 'users.read', db),
    ).rejects.toBeInstanceOf(PermissionDeniedError)
  })

  it('refuses a role without the permission and allows the right role', async () => {
    await makeStaff('sup', 'support')
    await expect(
      assertPermission(session('sup', 'sup@example.com'), 'billing.refund', db),
    ).rejects.toBeInstanceOf(PermissionDeniedError)
    const ctx = await assertPermission(
      session('sup', 'sup@example.com'),
      'tickets.reply',
      db,
    )
    expect(ctx.role).toBe('support')

    await makeStaff('fin', 'finance')
    await expect(
      assertPermission(session('fin', 'fin@example.com'), 'billing.refund', db),
    ).resolves.toMatchObject({ role: 'finance' })
  })

  it('refuses suspended staff', async () => {
    const staff = await makeStaff('sus', 'owner')
    await db.execute(
      sql`update "user" set status = 'suspended' where id = ${staff.id}`,
    )
    await expect(
      assertPermission(session('sus', 'sus@example.com'), 'users.read', db),
    ).rejects.toBeInstanceOf(PermissionDeniedError)
  })
})

describe('recordAudit', () => {
  it('rejects a blank reason before touching the database', async () => {
    const staff = await makeStaff('aud', 'admin')
    for (const reason of ['', '   ']) {
      await expect(
        recordAudit(
          db,
          { userId: staff.id },
          { action: 'users.suspend', targetType: 'user', reason },
        ),
      ).rejects.toBeInstanceOf(AuditReasonRequiredError)
    }
    const count = await db.execute(
      sql`select count(*)::int as n from audit_log`,
    )
    expect(count.rows[0].n).toBe(0)
  })

  it('writes a row with the trimmed reason', async () => {
    const staff = await makeStaff('aud2', 'admin')
    const row = await recordAudit(
      db,
      { userId: staff.id },
      {
        action: 'users.suspend',
        targetType: 'user',
        targetId: staff.id,
        reason: '  ticket 42  ',
        after: { status: 'suspended' },
      },
    )
    expect(row).toMatchObject({
      reason: 'ticket 42',
      action: 'users.suspend',
      after: { status: 'suspended' },
    })
  })
})
