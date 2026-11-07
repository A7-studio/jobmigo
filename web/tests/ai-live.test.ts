import { eq, sql } from 'drizzle-orm'
import { afterAll, beforeEach, describe, expect, it } from 'vitest'
import { z } from 'zod'
import { runTask } from '#/server/ai/gateway'
import { defineTask } from '#/server/ai/tasks'
import { getDb } from '#/server/db/client'
import { usageEvent } from '#/server/db/schema'
import { closeDb, resetData } from './helpers'

/**
 * Calls the real provider once with your own keys. Skipped unless
 * AI_LIVE_TEST=1, so Verify never spends money or needs a network.
 *   AI_LIVE_TEST=1 npm test -- tests/ai-live.test.ts
 */
const live = process.env.AI_LIVE_TEST === '1'
const db = getDb()

const task = defineTask({
  name: 'live-check',
  workflow: 'screen',
  tier: 'cheap',
  prompt: {
    version: 'v1',
    system: 'You answer arithmetic questions.',
    user: (input: { question: string }) =>
      `${input.question} Return JSON like {"answer": 4}.`,
  },
  input: z.object({ question: z.string() }),
  output: z.object({ answer: z.number() }),
})

beforeEach(resetData)
afterAll(closeDb)

describe.skipIf(!live)('live provider check', () => {
  it('gets a validated answer, records usage, then serves the cache', async () => {
    const rows = await db.execute(
      sql`insert into "user" (auth_subject, email) values ('live', 'live@example.com') returning id`,
    )
    const userId = rows.rows[0].id as string

    const first = await runTask(
      task,
      { question: 'What is 2 + 2?' },
      { userId },
    )
    expect(first.output.answer).toBe(4)
    expect(first.cacheHit).toBe(false)

    const second = await runTask(
      task,
      { question: 'What is 2 + 2?' },
      { userId },
    )
    expect(second.cacheHit).toBe(true)

    const events = await db
      .select()
      .from(usageEvent)
      .where(eq(usageEvent.userId, userId))
    expect(events).toHaveLength(2)
    expect(events.some((event) => event.tokensIn > 0)).toBe(true)
  })
})
