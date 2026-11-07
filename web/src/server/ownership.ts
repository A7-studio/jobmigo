import { and, eq } from 'drizzle-orm'
import type { PgColumn, PgTable } from 'drizzle-orm/pg-core'
import type { Db } from './db/client'

/** A tenant table: every row belongs to one user through `user_id`. */
export type OwnedTable = PgTable & { id: PgColumn; userId: PgColumn }

type Row<T extends OwnedTable> = T['$inferSelect']

/** The condition every tenant query must carry. */
export function ownedBy(table: OwnedTable, userId: string) {
  return eq(table.userId, userId)
}

const PROTECTED_COLUMNS = ['id', 'userId']

/** Drop the columns that decide ownership, so no caller can reassign a row. */
function withoutOwnership<TValues extends Record<string, unknown>>(
  values: TValues,
): TValues {
  return Object.fromEntries(
    Object.entries(values).filter(([key]) => !PROTECTED_COLUMNS.includes(key)),
  ) as TValues
}

function ownRow(table: OwnedTable, userId: string, id: string) {
  return and(eq(table.id, id), ownedBy(table, userId))
}

export async function findOwned<T extends OwnedTable>(
  db: Db,
  table: T,
  userId: string,
  id: string,
): Promise<Row<T> | null> {
  const t: OwnedTable = table
  const rows: unknown[] = await db
    .select()
    .from(t)
    .where(ownRow(t, userId, id))
    .limit(1)
  return (rows.at(0) as Row<T> | undefined) ?? null
}

export async function listOwned<T extends OwnedTable>(
  db: Db,
  table: T,
  userId: string,
): Promise<Row<T>[]> {
  const t: OwnedTable = table
  const rows: unknown[] = await db.select().from(t).where(ownedBy(t, userId))
  return rows as Row<T>[]
}

export async function updateOwned<T extends OwnedTable>(
  db: Db,
  table: T,
  userId: string,
  id: string,
  values: Partial<T['$inferInsert']>,
): Promise<Row<T> | null> {
  const t: OwnedTable = table
  const rows: unknown[] = await db
    .update(t)
    .set(withoutOwnership(values))
    .where(ownRow(t, userId, id))
    .returning()
  return (rows.at(0) as Row<T> | undefined) ?? null
}

export async function deleteOwned(
  db: Db,
  table: OwnedTable,
  userId: string,
  id: string,
): Promise<boolean> {
  const rows: unknown[] = await db
    .delete(table)
    .where(ownRow(table, userId, id))
    .returning({ id: table.id })
  return rows.length > 0
}
