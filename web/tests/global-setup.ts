import { drizzle } from 'drizzle-orm/node-postgres'
import { migrate } from 'drizzle-orm/node-postgres/migrator'
import { Client, Pool } from 'pg'

export const TEST_DB_SUFFIX = '_test'

export default async function setup() {
  const url = process.env.TEST_DATABASE_URL
  if (!url) throw new Error('Missing environment variable TEST_DATABASE_URL')
  const target = new URL(url)
  const name = target.pathname.slice(1)
  if (!name.endsWith(TEST_DB_SUFFIX)) {
    throw new Error(
      `Refusing to run tests: TEST_DATABASE_URL database "${name}" must end in "${TEST_DB_SUFFIX}".`,
    )
  }

  const admin = new URL(url)
  admin.pathname = '/postgres'
  const client = new Client({ connectionString: admin.toString() })
  await client.connect()
  const exists = await client.query(
    'select 1 from pg_database where datname = $1',
    [name],
  )
  if (exists.rowCount === 0) await client.query(`create database "${name}"`)
  await client.end()

  // Start from an empty schema so the baseline migration is what is tested.
  const pool = new Pool({ connectionString: url })
  await pool.query('drop schema if exists public cascade')
  await pool.query('drop schema if exists drizzle cascade')
  await pool.query('create schema public')
  await migrate(drizzle(pool), { migrationsFolder: './drizzle' })
  await pool.end()
}
