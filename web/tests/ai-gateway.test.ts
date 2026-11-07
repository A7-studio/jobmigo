import { eq, sql } from 'drizzle-orm'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { cacheKeyFor, canonicalJson, runTask } from '#/server/ai/gateway'
import type { AiProvider, AiRequest, AiResponse } from '#/server/ai/provider'
import { defineTask } from '#/server/ai/tasks'
import { getDb } from '#/server/db/client'
import { aiCache, usageEvent } from '#/server/db/schema'
import {
  AiInputInvalidError,
  AiNotConfiguredError,
  AiOutputInvalidError,
  AiUnavailableError,
} from '#/server/errors'
import { closeDb, resetData } from './helpers'

const db = getDb()
const ENV = {
  AI_CHEAP_MODEL: 'deepseek/model-a',
  AI_CHEAP_PRICE: '1,2',
  DEEPSEEK_API_KEY: 'test-key',
}

class FakeProvider implements AiProvider {
  readonly name = 'fake'
  readonly calls: AiRequest[] = []
  private readonly queue: (AiResponse | Error)[]

  constructor(...queue: (AiResponse | Error)[]) {
    this.queue = queue
  }

  complete(request: AiRequest): Promise<AiResponse> {
    this.calls.push(request)
    const next = this.queue.shift()
    if (!next) return Promise.reject(new Error('no response queued'))
    return next instanceof Error ? Promise.reject(next) : Promise.resolve(next)
  }
}

const reply = (text: string, tokensIn = 100, tokensOut = 50): AiResponse => ({
  text,
  tokensIn,
  tokensOut,
})

const task = defineTask({
  name: 'demo-parse',
  workflow: 'parse',
  tier: 'cheap',
  prompt: {
    version: 'v1',
    system: 'Extract the name.',
    user: (input: { text: string }) => `Text: ${input.text}`,
  },
  input: z.object({ text: z.string().min(1) }),
  output: z.object({ name: z.string() }),
})

async function makeUser(subject = 'sub_ai') {
  const rows = await db.execute(
    sql`insert into "user" (auth_subject, email) values (${subject}, ${`${subject}@example.com`}) returning id`,
  )
  return rows.rows[0].id as string
}

const events = (userId: string) =>
  db.select().from(usageEvent).where(eq(usageEvent.userId, userId))

beforeEach(resetData)
afterAll(closeDb)

describe('canonical hashing', () => {
  it('ignores key order and differs on content', () => {
    expect(canonicalJson({ b: 1, a: { d: 2, c: 3 } })).toBe(
      canonicalJson({ a: { c: 3, d: 2 }, b: 1 }),
    )
    expect(cacheKeyFor('t', 'v1', 'p/m', { a: 1 })).not.toBe(
      cacheKeyFor('t', 'v1', 'p/m', { a: 2 }),
    )
  })
})

describe('runTask', () => {
  it('calls the model, writes one usage event, and caches the output', async () => {
    const userId = await makeUser()
    const provider = new FakeProvider(reply('{"name":"Ada"}', 1000, 500))
    const result = await runTask(
      task,
      { text: 'hello' },
      {
        userId,
        env: ENV,
        provider,
      },
    )
    expect(result.output).toEqual({ name: 'Ada' })
    expect(result.cacheHit).toBe(false)
    expect(result.promptVersion).toBe('v1')
    expect(provider.calls).toHaveLength(1)
    expect(provider.calls[0].model).toBe('model-a')
    expect(provider.calls[0].system).toContain('single JSON object')

    const rows = await events(userId)
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({
      id: result.usageEventId,
      workflow: 'parse',
      provider: 'deepseek',
      model: 'model-a',
      promptVersion: 'v1',
      tokensIn: 1000,
      tokensOut: 500,
      cacheHit: false,
    })
    expect(Number(rows[0].costUsd)).toBeCloseTo(0.002, 6)
    expect(await db.select().from(aiCache)).toHaveLength(1)
  })

  it('serves the same input from the cache with no provider call', async () => {
    const userId = await makeUser()
    const first = new FakeProvider(reply('{"name":"Ada"}'))
    await runTask(
      task,
      { text: 'hello' },
      { userId, env: ENV, provider: first },
    )
    const second = new FakeProvider()
    const hit = await runTask(
      task,
      { text: 'hello' },
      {
        userId,
        env: ENV,
        provider: second,
      },
    )
    expect(hit.cacheHit).toBe(true)
    expect(hit.output).toEqual({ name: 'Ada' })
    expect(second.calls).toHaveLength(0)
    const rows = await events(userId)
    expect(rows).toHaveLength(2)
    const cached = rows.find((row) => row.cacheHit)
    expect(cached).toMatchObject({ tokensIn: 0, tokensOut: 0 })
    expect(Number(cached?.costUsd)).toBe(0)
  })

  it('never serves one user the cache of another', async () => {
    const alice = await makeUser('alice')
    const bob = await makeUser('bob')
    await runTask(
      task,
      { text: 'same' },
      {
        userId: alice,
        env: ENV,
        provider: new FakeProvider(reply('{"name":"Alice"}')),
      },
    )
    const provider = new FakeProvider(reply('{"name":"Bob"}'))
    const result = await runTask(
      task,
      { text: 'same' },
      {
        userId: bob,
        env: ENV,
        provider,
      },
    )
    expect(result.cacheHit).toBe(false)
    expect(result.output).toEqual({ name: 'Bob' })
    expect(provider.calls).toHaveLength(1)
  })

  it('misses when the prompt version or the model changes', async () => {
    const userId = await makeUser()
    await runTask(
      task,
      { text: 'x' },
      {
        userId,
        env: ENV,
        provider: new FakeProvider(reply('{"name":"A"}')),
      },
    )

    const bumped = defineTask({
      ...task,
      prompt: { ...task.prompt, version: 'v2' },
    })
    const p2 = new FakeProvider(reply('{"name":"B"}'))
    const r2 = await runTask(
      bumped,
      { text: 'x' },
      {
        userId,
        env: ENV,
        provider: p2,
      },
    )
    expect(r2.cacheHit).toBe(false)

    const p3 = new FakeProvider(reply('{"name":"C"}'))
    const r3 = await runTask(
      task,
      { text: 'x' },
      {
        userId,
        env: { ...ENV, AI_CHEAP_MODEL: 'deepseek/model-b' },
        provider: p3,
      },
    )
    expect(r3.cacheHit).toBe(false)
    expect(p3.calls).toHaveLength(1)
  })

  it('retries once on invalid output and records both calls', async () => {
    const userId = await makeUser()
    const provider = new FakeProvider(
      reply('not json at all', 10, 5),
      reply('{"name":"Ada"}', 20, 8),
    )
    const result = await runTask(
      task,
      { text: 'hello' },
      {
        userId,
        env: ENV,
        provider,
      },
    )
    expect(result.output).toEqual({ name: 'Ada' })
    expect(provider.calls).toHaveLength(2)
    expect(provider.calls[1].user).toContain('previous reply was rejected')
    expect(provider.calls[1].user).not.toContain('not json at all')
    expect(await events(userId)).toHaveLength(2)
  })

  it('fails visibly after a second invalid output and caches nothing', async () => {
    const userId = await makeUser()
    const provider = new FakeProvider(
      reply('{"wrong":1}'),
      reply('{"name":42}'),
    )
    await expect(
      runTask(task, { text: 'hello' }, { userId, env: ENV, provider }),
    ).rejects.toBeInstanceOf(AiOutputInvalidError)
    expect(await events(userId)).toHaveLength(2)
    expect(await db.select().from(aiCache)).toHaveLength(0)
  })

  it('throws ai_unavailable and writes no usage row when the provider fails', async () => {
    const userId = await makeUser()
    const provider = new FakeProvider(new AiUnavailableError())
    await expect(
      runTask(task, { text: 'hello' }, { userId, env: ENV, provider }),
    ).rejects.toBeInstanceOf(AiUnavailableError)
    expect(await events(userId)).toHaveLength(0)
  })

  it('rejects invalid input before any provider call', async () => {
    const userId = await makeUser()
    const provider = new FakeProvider()
    await expect(
      runTask(task, { text: '' }, { userId, env: ENV, provider }),
    ).rejects.toBeInstanceOf(AiInputInvalidError)
    expect(provider.calls).toHaveLength(0)
    expect(await events(userId)).toHaveLength(0)
  })

  it('fails before any call when the tier is not configured', async () => {
    const userId = await makeUser()
    const provider = new FakeProvider()
    await expect(
      runTask(task, { text: 'hello' }, { userId, env: {}, provider }),
    ).rejects.toBeInstanceOf(AiNotConfiguredError)
    expect(provider.calls).toHaveLength(0)
  })

  it('treats a cached value that no longer fits the schema as a miss', async () => {
    const userId = await makeUser()
    const key = cacheKeyFor('demo-parse', 'v1', 'deepseek/model-a', {
      text: 'hello',
    })
    await db.insert(aiCache).values({
      userId,
      cacheKey: key,
      task: 'demo-parse',
      promptVersion: 'v1',
      output: { shape: 'old' },
    })
    const provider = new FakeProvider(reply('{"name":"Fresh"}'))
    const result = await runTask(
      task,
      { text: 'hello' },
      {
        userId,
        env: ENV,
        provider,
      },
    )
    expect(result.cacheHit).toBe(false)
    expect(result.output).toEqual({ name: 'Fresh' })
    const rows = await db.select().from(aiCache)
    expect(rows).toHaveLength(1)
    expect(rows[0].output).toEqual({ name: 'Fresh' })
  })

  it('records a billed reply that has no content, then retries', async () => {
    const userId = await makeUser()
    const provider = new FakeProvider(
      reply('', 30, 0),
      reply('{"name":"Ada"}', 20, 8),
    )
    const result = await runTask(
      task,
      { text: 'hello' },
      {
        userId,
        env: ENV,
        provider,
      },
    )
    expect(result.output).toEqual({ name: 'Ada' })
    const rows = await events(userId)
    expect(rows).toHaveLength(2)
    expect(rows.map((row) => row.tokensIn).sort()).toEqual([20, 30])
  })

  it('passes the task time limit to the provider', async () => {
    const userId = await makeUser()
    const slow = defineTask({ ...task, name: 'slow', timeoutMs: 1234 })
    const provider = new FakeProvider(reply('{"name":"Ada"}'))
    await runTask(slow, { text: 'x' }, { userId, env: ENV, provider })
    expect(provider.calls[0].timeoutMs).toBe(1234)
  })

  it('records a null cost when no price is configured', async () => {
    const userId = await makeUser()
    await runTask(
      task,
      { text: 'hello' },
      {
        userId,
        env: { AI_CHEAP_MODEL: 'deepseek/model-a' },
        provider: new FakeProvider(reply('{"name":"Ada"}')),
      },
    )
    expect((await events(userId))[0].costUsd).toBeNull()
  })

  it('skips the cache for tasks that opt out', async () => {
    const userId = await makeUser()
    const fresh = defineTask({ ...task, name: 'no-cache', cache: false })
    const provider = new FakeProvider(
      reply('{"name":"One"}'),
      reply('{"name":"Two"}'),
    )
    await runTask(fresh, { text: 'x' }, { userId, env: ENV, provider })
    const second = await runTask(
      fresh,
      { text: 'x' },
      {
        userId,
        env: ENV,
        provider,
      },
    )
    expect(second.cacheHit).toBe(false)
    expect(second.output).toEqual({ name: 'Two' })
    expect(await db.select().from(aiCache)).toHaveLength(0)
  })

  it('never logs the input or the model output', async () => {
    const userId = await makeUser()
    const lines: string[] = []
    const spy = vi.spyOn(console, 'log').mockImplementation((l: string) => {
      lines.push(l)
    })
    const warn = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    await runTask(
      task,
      { text: 'cv-secret-text' },
      {
        userId,
        env: ENV,
        provider: new FakeProvider(
          reply('garbage reply-secret'),
          reply('{"name":"output-secret"}'),
        ),
      },
    )
    spy.mockRestore()
    warn.mockRestore()
    const logged = lines.join('\n')
    expect(logged).toContain('ai task')
    for (const secret of [
      'cv-secret-text',
      'reply-secret',
      'output-secret',
      'test-key',
    ]) {
      expect(logged).not.toContain(secret)
    }
  })
})
