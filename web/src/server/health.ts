import { sql } from 'drizzle-orm'
import { getDb } from './db/client'
import type { Db } from './db/client'

export function healthResponse(): Response {
  return Response.json({ status: 'ok' })
}

export async function readinessResponse(db: Pick<Db, 'execute'> = getDb()) {
  try {
    await db.execute(sql`select 1`)
    return Response.json({ status: 'ok' })
  } catch {
    return Response.json(
      {
        error: {
          code: 'unavailable',
          message: 'The database is not reachable.',
        },
      },
      { status: 503 },
    )
  }
}
