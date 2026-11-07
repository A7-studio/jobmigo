import { sql } from 'drizzle-orm'
import { pgTable, text, uuid } from 'drizzle-orm/pg-core'
import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import { getDb } from '#/server/db/client'
import { user } from '#/server/db/schema'
import { PermissionDeniedError, UnauthorizedError } from '#/server/errors'
import { healthResponse, readinessResponse } from '#/server/health'
import { requireUser } from '#/server/identity'
import { meFromHeaders } from '#/server/me'
import { updateOwned } from '#/server/ownership'
import { requirePermission } from '#/server/permissions'
import { withRequestId } from '#/server/request-id'
import { closeDb, resetData } from './helpers'

const getSession = vi.hoisted(() => vi.fn())
vi.mock('#/lib/auth', () => ({ auth: { api: { getSession } } }))

const db = getDb()
const headers = new Headers({ cookie: 'session=abc' })
const session = (id = 'ba_1') => ({
  user: { id, email: `${id}@example.com`, name: id },
})

const note = pgTable('wiring_note', {
  id: uuid('id').primaryKey().defaultRandom(),
  userId: uuid('user_id').notNull(),
  body: text('body').notNull(),
})

beforeAll(async () => {
  await db.execute(sql`create table if not exists wiring_note (
    id uuid primary key default gen_random_uuid(), user_id uuid not null, body text not null)`)
})
beforeEach(async () => {
  await resetData()
  getSession.mockReset()
})
afterAll(async () => {
  await db.execute(sql`drop table if exists wiring_note`)
  await closeDb()
})

describe('requireUser with the real wiring', () => {
  it('passes the request headers to Better Auth and returns the app user', async () => {
    getSession.mockResolvedValue(session())
    const row = await requireUser(headers)
    expect(row.authSubject).toBe('ba_1')
    expect(getSession).toHaveBeenCalledWith({ headers })
  })

  it('refuses a request without a session', async () => {
    getSession.mockResolvedValue(null)
    await expect(requireUser(headers)).rejects.toBeInstanceOf(UnauthorizedError)
  })

  it('refuses a suspended user', async () => {
    getSession.mockResolvedValue(session())
    await requireUser(headers)
    await db.execute(sql`update "user" set status = 'suspended'`)
    await expect(requireUser(headers)).rejects.toBeInstanceOf(
      PermissionDeniedError,
    )
  })
})

describe('requirePermission with the real wiring', () => {
  it('refuses non-staff and allows the right role', async () => {
    getSession.mockResolvedValue(session('plain'))
    await expect(
      requirePermission(headers, 'users.read'),
    ).rejects.toBeInstanceOf(PermissionDeniedError)
    const [row] = await db.select().from(user)
    await db.execute(
      sql`insert into staff_member (user_id, role_id)
          select ${row.id}, id from role where name = 'support'`,
    )
    await expect(
      requirePermission(headers, 'users.read'),
    ).resolves.toMatchObject({
      role: 'support',
    })
    await expect(
      requirePermission(headers, 'billing.refund'),
    ).rejects.toBeInstanceOf(PermissionDeniedError)
  })
})

describe('getMe path', () => {
  it('builds the result from the request session', async () => {
    getSession.mockResolvedValue(session())
    const result = await meFromHeaders(headers)
    expect(result).toMatchObject({
      ok: true,
      me: { email: 'ba_1@example.com', staff: null },
    })
    getSession.mockResolvedValue(null)
    expect(await meFromHeaders(headers)).toMatchObject({
      ok: false,
      code: 'unauthorized',
    })
  })
})

describe('request id', () => {
  const next = () => Promise.resolve({ response: new Response('ok') })

  it('keeps a supplied id and generates one otherwise', async () => {
    const kept = await withRequestId(
      new Request('http://x', { headers: { 'x-request-id': 'abc-123' } }),
      next,
    )
    expect(kept.response.headers.get('x-request-id')).toBe('abc-123')
    const made = await withRequestId(new Request('http://x'), next)
    expect(made.response.headers.get('x-request-id')).toMatch(/^[0-9a-f-]{36}$/)
  })
})

describe('health routes', () => {
  it('reports ok and readiness, and 503 with the stable shape when the database fails', async () => {
    expect(await healthResponse().json()).toEqual({ status: 'ok' })
    expect(await (await readinessResponse(db)).json()).toEqual({ status: 'ok' })
    const failing = { execute: () => Promise.reject(new Error('down')) }
    const response = await readinessResponse(failing as never)
    expect(response.status).toBe(503)
    expect(await response.json()).toEqual({
      error: { code: 'unavailable', message: 'The database is not reachable.' },
    })
  })
})

describe('updateOwned cannot reassign ownership (F-05)', () => {
  it('ignores userId and id in the values', async () => {
    const [a, b] = await db
      .insert(user)
      .values([
        { authSubject: 'a', email: 'a@example.com' },
        { authSubject: 'b', email: 'b@example.com' },
      ])
      .returning()
    const [mine] = await db
      .insert(note)
      .values({ userId: a.id, body: 'mine' })
      .returning()
    const updated = await updateOwned(db, note, a.id, mine.id, {
      body: 'edited',
      userId: b.id,
      id: '00000000-0000-0000-0000-000000000000',
    })
    expect(updated).toMatchObject({ id: mine.id, userId: a.id, body: 'edited' })
  })
})
