import { sql } from 'drizzle-orm'
import { pgTable, text, uuid } from 'drizzle-orm/pg-core'
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { getDb } from '#/server/db/client'
import { user } from '#/server/db/schema'
import {
  deleteOwned,
  findOwned,
  listOwned,
  updateOwned,
} from '#/server/ownership'
import { closeDb, resetData } from './helpers'

const db = getDb()

// A tenant table that exists only in tests; real tenant tables arrive with later features.
const note = pgTable('test_note', {
  id: uuid('id').primaryKey().defaultRandom(),
  userId: uuid('user_id')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
  body: text('body').notNull(),
})

beforeAll(async () => {
  await db.execute(sql`create table if not exists test_note (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references "user" (id) on delete cascade,
    body text not null)`)
})
beforeEach(resetData)
afterAll(async () => {
  await db.execute(sql`drop table if exists test_note`)
  await closeDb()
})

async function seed() {
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
  const [theirs] = await db
    .insert(note)
    .values({ userId: b.id, body: 'theirs' })
    .returning()
  return { a, b, mine, theirs }
}

describe('owner scoping helpers', () => {
  it('reads own rows and never another user’s', async () => {
    const { a, mine, theirs } = await seed()
    expect((await findOwned(db, note, a.id, mine.id))?.body).toBe('mine')
    expect(await findOwned(db, note, a.id, theirs.id)).toBeNull()
    expect((await listOwned(db, note, a.id)).map((r) => r.body)).toEqual([
      'mine',
    ])
  })

  it('cannot update another user’s row', async () => {
    const { a, theirs } = await seed()
    expect(
      await updateOwned(db, note, a.id, theirs.id, { body: 'hacked' }),
    ).toBeNull()
    const rows = await db.execute(
      sql`select body from test_note where id = ${theirs.id}`,
    )
    expect(rows.rows[0].body).toBe('theirs')
  })

  it('updates own rows', async () => {
    const { a, mine } = await seed()
    expect(
      (await updateOwned(db, note, a.id, mine.id, { body: 'edited' }))?.body,
    ).toBe('edited')
  })

  it('cannot delete another user’s row but can delete its own', async () => {
    const { a, mine, theirs } = await seed()
    expect(await deleteOwned(db, note, a.id, theirs.id)).toBe(false)
    expect(await deleteOwned(db, note, a.id, mine.id)).toBe(true)
    const left = await db.execute(sql`select count(*)::int as n from test_note`)
    expect(left.rows[0].n).toBe(1)
  })
})
