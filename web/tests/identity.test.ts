import { sql } from 'drizzle-orm'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { getDb } from '#/server/db/client'
import { logger } from '#/server/logger'
import { buildMe } from '#/server/me'
import { resolveUser } from '#/server/identity'
import {
  ConflictError,
  PermissionDeniedError,
  UnauthorizedError,
  toResult,
} from '#/server/errors'
import { closeDb, resetData } from './helpers'

const db = getDb()
const session = (id = 'ba_1', email = 'Sam@Example.com', name = 'Sam') => ({
  user: { id, email, name },
})

beforeEach(resetData)
afterAll(closeDb)

describe('resolveUser', () => {
  it('creates the user on first request with defaults and a lowercase email', async () => {
    const row = await resolveUser(session(), db)
    expect(row).toMatchObject({
      authSubject: 'ba_1',
      email: 'sam@example.com',
      displayName: 'Sam',
      locale: 'en',
      timezone: 'Africa/Nairobi',
      status: 'active',
    })
  })

  it('returns the same row on later requests', async () => {
    const first = await resolveUser(session(), db)
    const second = await resolveUser(session(), db)
    expect(second.id).toBe(first.id)
  })

  it('creates one row for concurrent first requests', async () => {
    const rows = await Promise.all(
      Array.from({ length: 6 }, () => resolveUser(session(), db)),
    )
    expect(new Set(rows.map((r) => r.id)).size).toBe(1)
    const count = await db.execute(sql`select count(*)::int as n from "user"`)
    expect(count.rows[0].n).toBe(1)
  })

  it('rejects a missing session as unauthorized', async () => {
    await expect(resolveUser(null, db)).rejects.toBeInstanceOf(
      UnauthorizedError,
    )
  })

  it('rejects suspended and deleted users as forbidden', async () => {
    for (const status of ['suspended', 'deleted']) {
      await resetData()
      await resolveUser(session(), db)
      await db.execute(sql`update "user" set status = ${status}`)
      await expect(resolveUser(session(), db)).rejects.toBeInstanceOf(
        PermissionDeniedError,
      )
    }
  })

  it('refuses an email that belongs to another identity', async () => {
    await resolveUser(session('ba_1', 'same@example.com'), db)
    await expect(
      resolveUser(session('ba_2', 'Same@Example.com'), db),
    ).rejects.toBeInstanceOf(ConflictError)
  })
})

describe('buildMe', () => {
  it('returns the user without auth_subject and staff null', async () => {
    const result = await buildMe(session(), db)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.me).toEqual({
      id: expect.any(String),
      email: 'sam@example.com',
      displayName: 'Sam',
      locale: 'en',
      timezone: 'Africa/Nairobi',
      staff: null,
    })
    expect(JSON.stringify(result)).not.toContain('ba_1')
  })

  it('includes the staff role and its permissions', async () => {
    const result = await buildMe(session(), db)
    if (!result.ok) throw new Error('expected ok')
    await db.execute(
      sql`insert into staff_member (user_id, role_id)
          select ${result.me.id}, id from role where name = 'support'`,
    )
    const staff = await buildMe(session(), db)
    if (!staff.ok) throw new Error('expected ok')
    expect(staff.me.staff).toEqual({
      role: 'support',
      permissions: [
        'overview.read',
        'tickets.read',
        'tickets.reply',
        'users.read',
      ],
    })
  })

  it('maps errors to the stable shape', async () => {
    expect(await buildMe(null, db)).toEqual({
      ok: false,
      code: 'unauthorized',
      message: 'Sign in to continue.',
    })
    await resolveUser(session(), db)
    await db.execute(sql`update "user" set status = 'suspended'`)
    const forbidden = await buildMe(session(), db)
    expect(forbidden).toMatchObject({ ok: false, code: 'forbidden' })
  })
})

describe('toResult and logging', () => {
  it('hides unexpected errors behind internal_error and logs them without details', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const result = toResult(new Error('secret@example.com token=abc'))
    expect(result).toEqual({
      status: 500,
      code: 'internal_error',
      message: 'Something went wrong.',
    })
    const line = String(spy.mock.calls[0][0])
    expect(JSON.parse(line)).toMatchObject({
      level: 'error',
      message: 'unhandled error',
    })
    expect(line).not.toContain('secret@example.com')
    expect(line).not.toContain('token=abc')
    spy.mockRestore()
  })

  it('writes one JSON line with the request id when one is set', async () => {
    const { runWithRequestId } = await import('#/server/logger')
    const spy = vi.spyOn(console, 'log').mockImplementation(() => undefined)
    runWithRequestId('req-1', () => logger.info('hello', { userId: 'u1' }))
    expect(JSON.parse(String(spy.mock.calls[0][0]))).toMatchObject({
      level: 'info',
      message: 'hello',
      requestId: 'req-1',
      userId: 'u1',
    })
    spy.mockRestore()
  })
})
