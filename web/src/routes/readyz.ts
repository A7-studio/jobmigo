import { createFileRoute } from '@tanstack/react-router'
import { sql } from 'drizzle-orm'
import { getDb } from '#/server/db/client'

export const Route = createFileRoute('/readyz')({
  server: {
    handlers: {
      GET: async () => {
        try {
          await getDb().execute(sql`select 1`)
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
      },
    },
  },
})
