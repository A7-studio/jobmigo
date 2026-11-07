import { sql } from 'drizzle-orm'
import { afterAll, beforeEach, describe, expect, it } from 'vitest'
import { getDb } from '#/server/db/client'
import { closeDb, resetData } from './helpers'

const db = getDb()

/** Drizzle wraps driver errors; the database message lives on `cause`. */
async function dbError(run: Promise<unknown>): Promise<string> {
  try {
    await run
  } catch (error) {
    const cause = (error as { cause?: { message?: string } }).cause
    return cause?.message ?? String(error)
  }
  throw new Error('expected the statement to fail')
}

const COLUMNS: Record<string, string[]> = {
  user: [
    'id',
    'auth_subject',
    'email',
    'display_name',
    'locale',
    'timezone',
    'status',
    'created_at',
    'updated_at',
  ],
  role: ['id', 'name'],
  role_permission: ['role_id', 'permission'],
  staff_member: ['user_id', 'role_id', 'mfa_enforced', 'created_at'],
  audit_log: [
    'id',
    'staff_id',
    'action',
    'target_type',
    'target_id',
    'before',
    'after',
    'reason',
    'ip',
    'at',
  ],
  auth_user: [
    'id',
    'name',
    'email',
    'email_verified',
    'image',
    'created_at',
    'updated_at',
  ],
  auth_session: [
    'id',
    'expires_at',
    'token',
    'created_at',
    'updated_at',
    'ip_address',
    'user_agent',
    'user_id',
  ],
  auth_account: [
    'id',
    'account_id',
    'provider_id',
    'user_id',
    'access_token',
    'refresh_token',
    'id_token',
    'access_token_expires_at',
    'refresh_token_expires_at',
    'scope',
    'password',
    'created_at',
    'updated_at',
  ],
  usage_event: [
    'id',
    'user_id',
    'workflow',
    'provider',
    'model',
    'prompt_version',
    'tokens_in',
    'tokens_out',
    'cost_usd',
    'cache_hit',
    'created_at',
  ],
  ai_cache: [
    'user_id',
    'cache_key',
    'task',
    'prompt_version',
    'output',
    'created_at',
  ],
  auth_verification: [
    'id',
    'identifier',
    'value',
    'expires_at',
    'created_at',
    'updated_at',
  ],
}

const MATRIX: Record<string, string[]> = {
  support: ['overview.read', 'users.read', 'tickets.read', 'tickets.reply'],
  finance: [
    'overview.read',
    'users.read',
    'billing.read',
    'billing.refund',
    'pricing.write',
  ],
}

async function makeStaff(subject = 'sub_1', email = 'a@example.com') {
  const rows = await db.execute(
    sql`insert into "user" (auth_subject, email) values (${subject}, ${email}) returning id`,
  )
  const userId = rows.rows[0].id as string
  await db.execute(
    sql`insert into staff_member (user_id, role_id)
        select ${userId}, id from role where name = 'support'`,
  )
  return userId
}

beforeEach(resetData)
afterAll(closeDb)

describe('tables', () => {
  for (const [table, columns] of Object.entries(COLUMNS)) {
    it(`${table} has the expected columns`, async () => {
      const rows = await db.execute(
        sql`select column_name from information_schema.columns where table_name = ${table}`,
      )
      expect(rows.rows.map((r) => r.column_name as string).sort()).toEqual(
        [...columns].sort(),
      )
    })
  }

  it('does not create a JWKS table', async () => {
    const rows = await db.execute(
      sql`select 1 from information_schema.tables where table_name = 'auth_jwks'`,
    )
    expect(rows.rowCount).toBe(0)
  })
})

describe('seed data', () => {
  it('seeds the four roles', async () => {
    const rows = await db.execute(sql`select name from role order by name`)
    expect(rows.rows.map((r) => r.name)).toEqual([
      'admin',
      'finance',
      'owner',
      'support',
    ])
  })

  async function permissionsOf(name: string) {
    const rows = await db.execute(
      sql`select p.permission from role_permission p join role r on r.id = p.role_id
          where r.name = ${name} order by p.permission`,
    )
    return rows.rows.map((r) => r.permission as string)
  }

  it('gives support and finance their frozen permissions', async () => {
    for (const [name, perms] of Object.entries(MATRIX)) {
      expect(await permissionsOf(name)).toEqual([...perms].sort())
    }
  })

  it('gives owner all thirteen and admin all but refund and pricing', async () => {
    const owner = await permissionsOf('owner')
    expect(owner).toHaveLength(13)
    expect(await permissionsOf('admin')).toEqual(
      owner.filter((p) => p !== 'billing.refund' && p !== 'pricing.write'),
    )
  })
})

describe('user table', () => {
  it('applies defaults', async () => {
    const rows = await db.execute(
      sql`insert into "user" (auth_subject, email) values ('s', 'b@example.com')
          returning locale, timezone, status, created_at`,
    )
    expect(rows.rows[0]).toMatchObject({
      locale: 'en',
      timezone: 'Africa/Nairobi',
      status: 'active',
    })
    expect(rows.rows[0].created_at).toBeTruthy()
  })

  it('rejects an unknown status', async () => {
    await expect(
      db.execute(
        sql`insert into "user" (auth_subject, email, status) values ('s', 'c@example.com', 'banned')`,
      ),
    ).rejects.toThrow()
  })

  it('enforces unique auth_subject and email', async () => {
    await db.execute(
      sql`insert into "user" (auth_subject, email) values ('s', 'd@example.com')`,
    )
    await expect(
      db.execute(
        sql`insert into "user" (auth_subject, email) values ('s', 'e@example.com')`,
      ),
    ).rejects.toThrow()
    await expect(
      db.execute(
        sql`insert into "user" (auth_subject, email) values ('t', 'd@example.com')`,
      ),
    ).rejects.toThrow()
  })
})

describe('audit_log', () => {
  async function addEntry(reason: string) {
    const staff = await makeStaff()
    return db.execute(
      sql`insert into audit_log (staff_id, action, target_type, reason)
          values (${staff}, 'users.suspend', 'user', ${reason}) returning id`,
    )
  }

  it('rejects an empty or whitespace reason', async () => {
    await expect(addEntry('   ')).rejects.toThrow()
  })

  it('is append-only', async () => {
    const rows = await addEntry('Checked the ticket')
    const id = rows.rows[0].id as string
    expect(
      await dbError(
        db.execute(sql`update audit_log set reason = 'x' where id = ${id}`),
      ),
    ).toMatch(/append-only/)
    expect(
      await dbError(db.execute(sql`delete from audit_log where id = ${id}`)),
    ).toMatch(/append-only/)
  })
})

describe('ai ledger tables', () => {
  async function makeUser() {
    const rows = await db.execute(
      sql`insert into "user" (auth_subject, email) values ('sub_ai', 'ai@example.com') returning id`,
    )
    return rows.rows[0].id as string
  }
  const insertEvent = (userId: string, workflow: string, tokensIn: number) =>
    db.execute(
      sql`insert into usage_event (user_id, workflow, provider, model, prompt_version, tokens_in, tokens_out, cache_hit)
          values (${userId}, ${workflow}, 'p', 'm', 'v1', ${tokensIn}, 0, false)`,
    )

  it('rejects an unknown workflow', async () => {
    const userId = await makeUser()
    expect(await dbError(insertEvent(userId, 'chat', 1))).toContain(
      'ck_usage_event_workflow',
    )
  })

  it('rejects negative token counts', async () => {
    const userId = await makeUser()
    expect(await dbError(insertEvent(userId, 'parse', -1))).toContain(
      'ck_usage_event_tokens',
    )
  })

  it('allows a null cost and removes rows with the user', async () => {
    const userId = await makeUser()
    await insertEvent(userId, 'parse', 10)
    await db.execute(
      sql`insert into ai_cache (user_id, cache_key, task, prompt_version, output)
          values (${userId}, 'k', 't', 'v1', '{}'::jsonb)`,
    )
    await db.execute(sql`delete from "user" where id = ${userId}`)
    const events = await db.execute(sql`select 1 from usage_event`)
    const cache = await db.execute(sql`select 1 from ai_cache`)
    expect(events.rowCount).toBe(0)
    expect(cache.rowCount).toBe(0)
  })
})
