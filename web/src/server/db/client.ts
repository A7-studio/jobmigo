import { drizzle } from 'drizzle-orm/node-postgres'
import type { NodePgDatabase } from 'drizzle-orm/node-postgres'
import { Pool } from 'pg'
import * as schema from './schema'

export type Db = NodePgDatabase<typeof schema>

let pool: Pool | undefined
let instance: Db | undefined

export function getPool(): Pool {
  if (!pool) {
    const url = process.env.DATABASE_URL
    if (!url) throw new Error('Missing environment variable DATABASE_URL')
    pool = new Pool({ connectionString: url })
  }
  return pool
}

export function getDb(): Db {
  instance ??= drizzle(getPool(), { schema })
  return instance
}
