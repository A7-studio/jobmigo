import { sql } from 'drizzle-orm'
import { afterAll, beforeEach, describe, expect, it } from 'vitest'
import { flushPendingSends } from '#/server/waitlist'
import { getDb } from '#/server/db/client'
import { createRateLimiter } from '#/server/rate-limit'
import type { EmailMessage, EmailProvider } from '#/server/mail'
import { clientIp, handleJoin } from '#/server/waitlist-api'
import { closeDb, resetData } from './helpers'

const db = getDb()
const sent: EmailMessage[] = []
const mail: EmailProvider = {
  send: (m) => {
    sent.push(m)
    return Promise.resolve()
  },
}
const deps = { db, mail, baseUrl: 'https://jobmigo.test' }
const headers = (init: Record<string, string> = {}) => new Headers(init)
const open = createRateLimiter({ max: 1_000_000, windowMs: 1000 })
const input = (over = {}) => ({
  email: 'sam@example.com',
  consent: true,
  ...over,
})

beforeEach(async () => {
  await resetData()
  sent.length = 0
})
afterAll(closeDb)

describe('clientIp', () => {
  it('ignores both headers unless proxy headers are trusted', () => {
    const h = headers({
      'cf-connecting-ip': '1.1.1.1',
      'x-forwarded-for': '2.2.2.2',
    })
    expect(clientIp(h, false)).toBeNull()
    expect(clientIp(headers(), false)).toBeNull()
  })

  it('returns cf-connecting-ip when trusted and never x-forwarded-for', () => {
    expect(
      clientIp(
        headers({
          'cf-connecting-ip': '1.1.1.1',
          'x-forwarded-for': '2.2.2.2',
        }),
        true,
      ),
    ).toBe('1.1.1.1')
    expect(clientIp(headers({ 'x-forwarded-for': '2.2.2.2' }), true)).toBeNull()
  })
})

describe('handleJoin', () => {
  it('returns ok for the honeypot without storing or sending', async () => {
    const result = await handleJoin(
      input({ website: 'http://spam' }),
      headers(),
      { deps },
    )
    await flushPendingSends()
    expect(result).toEqual({ ok: true })
    expect(sent).toHaveLength(0)
    const rows = await db.execute(
      sql`select count(*)::int as n from waitlist_signup`,
    )
    expect(rows.rows[0].n).toBe(0)
  })

  it('rate limits the sixth join from one address', async () => {
    const limiter = createRateLimiter({ max: 5, windowMs: 600_000 })
    const h = headers({ 'cf-connecting-ip': '9.9.9.9' })
    for (let i = 0; i < 5; i++) {
      expect(
        await handleJoin(input({ email: `u${i}@example.com` }), h, {
          limiter,
          globalLimiter: open,
          trustProxy: true,
          deps,
        }),
      ).toEqual({ ok: true })
    }
    expect(
      await handleJoin(input({ email: 'u6@example.com' }), h, {
        limiter,
        globalLimiter: open,
        trustProxy: true,
        deps,
      }),
    ).toMatchObject({
      ok: false,
      code: 'rate_limited',
    })
    const other = headers({ 'cf-connecting-ip': '8.8.8.8' })
    expect(
      await handleJoin(input({ email: 'u7@example.com' }), other, {
        limiter,
        globalLimiter: open,
        trustProxy: true,
        deps,
      }),
    ).toEqual({ ok: true })
  })

  it('returns the stable error shapes', async () => {
    const limiter = createRateLimiter({ max: 99, windowMs: 1000 })
    expect(
      await handleJoin(input({ email: 'bad' }), headers(), {
        limiter,
        globalLimiter: open,
        trustProxy: true,
        deps,
      }),
    ).toMatchObject({
      ok: false,
      code: 'invalid_email',
      message: expect.any(String),
    })
    expect(
      await handleJoin(input({ consent: false }), headers(), {
        limiter,
        globalLimiter: open,
        trustProxy: true,
        deps,
      }),
    ).toMatchObject({
      ok: false,
      code: 'consent_required',
    })
  })

  it('skips the per-IP limit without a trusted address and caps everyone globally', async () => {
    const globalLimiter = createRateLimiter({ max: 60, windowMs: 600_000 })
    const h = headers({ 'x-forwarded-for': '7.7.7.7' })
    for (let i = 0; i < 60; i++) {
      expect(
        await handleJoin(input({ email: `g${i}@example.com` }), h, {
          globalLimiter,
          trustProxy: false,
          deps,
        }),
      ).toEqual({ ok: true })
    }
    expect(
      await handleJoin(input({ email: 'g61@example.com' }), h, {
        globalLimiter,
        trustProxy: false,
        deps,
      }),
    ).toMatchObject({
      ok: false,
      code: 'rate_limited',
    })
    await flushPendingSends()
  })
})

describe('confirm page', () => {
  it('does not confirm on load: the route has no loader and only the button calls the server function', async () => {
    const { readFileSync } = await import('node:fs')
    const source = readFileSync('src/routes/waitlist/confirm.tsx', 'utf8')
    expect(source).not.toMatch(/loader\s*:/)
    expect(source.match(/confirmWaitlistFn\(/g)).toHaveLength(1)
    expect(source).toContain('onClick')
  })
})
