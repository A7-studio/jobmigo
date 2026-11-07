// Applies the SQL migrations in ./drizzle. Plain ESM so the production image can run
// it without dev dependencies. Exits non-zero on any failure and never prints the URL.
import pg from 'pg'
import { drizzle } from 'drizzle-orm/node-postgres'
import { migrate } from 'drizzle-orm/node-postgres/migrator'

const url = process.env.DATABASE_URL
if (!url) {
  console.error('migrate: DATABASE_URL is not set')
  process.exit(1)
}

const pool = new pg.Pool({ connectionString: url, connectionTimeoutMillis: 10_000 })
try {
  await migrate(drizzle(pool), {
    migrationsFolder: process.env.MIGRATIONS_FOLDER ?? './drizzle',
  })
  console.log('migrate: migrations applied')
} catch (error) {
  const cause = error instanceof Error ? error.cause : undefined
  const detail = cause instanceof Error ? cause.message : error instanceof Error ? error.message : 'unknown error'
  console.error(`migrate: failed: ${detail}`)
  process.exitCode = 1
} finally {
  await pool.end()
}
