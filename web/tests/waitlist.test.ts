import { eq, sql } from 'drizzle-orm'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { getDb } from '#/server/db/client'
import { waitlistSignup } from '#/server/db/schema'
import { ResendProvider } from '#/server/mail'
import type { EmailMessage, EmailProvider } from '#/server/mail'
import { createRateLimiter } from '#/server/rate-limit'
import {
  confirmWaitlist,
  flushPendingSends,
  hashToken,
  joinWaitlist as joinRaw,
  unsubscribeWaitlist,
} from '#/server/waitlist'
import type { JoinInput, WaitlistDeps } from '#/server/waitlist'
import { closeDb, resetData } from './helpers'

const db = getDb()
const BASE = 'https://jobmigo.test'

let clock = new Date('2026-11-07T10:00:00Z')
const advance = (ms: number) => {
  clock = new Date(clock.getTime() + ms)
}
const MIN = 60 * 1000
const DAY = 24 * 60 * MIN

class FakeMail implements EmailProvider {
  sent: EmailMessage[] = []
  fail = false
  send(message: EmailMessage) {
    if (this.fail) return Promise.reject(new Error('provider down'))
    this.sent.push(message)
    return Promise.resolve()
  }
}

/** Join, then wait for the background email so tests can inspect what was sent. */
async function joinWaitlist(input: JoinInput, deps: WaitlistDeps) {
  const result = await joinRaw(input, deps)
  await flushPendingSends()
  return result
}

let mail: FakeMail
const deps = () => ({ db, mail, now: () => clock, baseUrl: BASE })
const tokenOf = (message: EmailMessage) =>
  /confirm\?token=([\w-]+)/.exec(message.text)?.[1] ?? ''
const rowFor = async (email: string) =>
  (
    await db
      .select()
      .from(waitlistSignup)
      .where(eq(waitlistSignup.email, email))
  )[0]

beforeEach(async () => {
  await resetData()
  mail = new FakeMail()
  clock = new Date('2026-11-07T10:00:00Z')
})
afterAll(closeDb)

describe('joinWaitlist', () => {
  it('creates a pending row and sends one email with the token links', async () => {
    const result = await joinWaitlist(
      { email: 'sam@example.com', consent: true },
      deps(),
    )
    expect(result).toEqual({ ok: true })
    expect(mail.sent).toHaveLength(1)
    const token = tokenOf(mail.sent[0])
    expect(token).toHaveLength(43)
    expect(mail.sent[0].text).toContain(
      `${BASE}/waitlist/unsubscribe?token=${token}`,
    )
    expect(mail.sent[0].headers?.['List-Unsubscribe']).toBe(
      `<${BASE}/waitlist/unsubscribe?token=${token}>`,
    )
    const row = await rowFor('sam@example.com')
    expect(row).toMatchObject({
      status: 'pending',
      consentTextVersion: 'waitlist-v1',
      emailsSent: 1,
    })
    expect(row.consentedAt).toEqual(clock)
  })

  it('stores only a hash of the token', async () => {
    await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
    const token = tokenOf(mail.sent[0])
    const row = await rowFor('sam@example.com')
    expect(row.tokenHash).toBe(hashToken(token))
    const dump = await db.execute(sql`select * from waitlist_signup`)
    expect(JSON.stringify(dump.rows)).not.toContain(token)
  })

  it('trims and lowercases the email', async () => {
    await joinWaitlist({ email: '  Sam@Example.COM ', consent: true }, deps())
    expect(await rowFor('sam@example.com')).toBeDefined()
  })

  it('rejects invalid or overlong emails and missing consent', async () => {
    const long = `${'a'.repeat(250)}@example.com`
    for (const email of ['', 'nope', 'a@b', long]) {
      expect(
        await joinWaitlist({ email, consent: true }, deps()),
      ).toMatchObject({
        ok: false,
        code: 'invalid_email',
      })
    }
    expect(
      await joinWaitlist({ email: 'sam@example.com', consent: false }, deps()),
    ).toMatchObject({
      ok: false,
      code: 'consent_required',
    })
    expect(mail.sent).toHaveLength(0)
    const count = await db.execute(
      sql`select count(*)::int as n from waitlist_signup`,
    )
    expect(count.rows[0].n).toBe(0)
  })

  it('keeps a clean source and drops a bad one', async () => {
    await joinWaitlist(
      { email: 'a@example.com', consent: true, source: 'LinkedIn_Nov' },
      deps(),
    )
    await joinWaitlist(
      { email: 'b@example.com', consent: true, source: '<script>' },
      deps(),
    )
    await joinWaitlist(
      { email: 'c@example.com', consent: true, source: 'x'.repeat(65) },
      deps(),
    )
    expect((await rowFor('a@example.com')).source).toBe('linkedin_nov')
    expect((await rowFor('b@example.com')).source).toBeNull()
    expect((await rowFor('c@example.com')).source).toBeNull()
  })

  it('sends nothing for a repeat within 10 minutes and resends after', async () => {
    await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
    const first = tokenOf(mail.sent[0])
    advance(5 * MIN)
    expect(
      await joinWaitlist({ email: 'sam@example.com', consent: true }, deps()),
    ).toEqual({
      ok: true,
    })
    expect(mail.sent).toHaveLength(1)

    advance(6 * MIN)
    await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
    expect(mail.sent).toHaveLength(2)
    const second = tokenOf(mail.sent[1])
    expect(second).not.toBe(first)
    expect(await confirmWaitlist(first, deps())).toBe('invalid')
    expect(await confirmWaitlist(second, deps())).toBe('confirmed')
  })

  it('stops after five emails', async () => {
    for (let i = 0; i < 8; i++) {
      await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
      advance(11 * MIN)
    }
    expect(mail.sent).toHaveLength(5)
  })

  it('sends nothing to a confirmed address and gives the same result', async () => {
    await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
    await confirmWaitlist(tokenOf(mail.sent[0]), deps())
    advance(DAY)
    expect(
      await joinWaitlist({ email: 'sam@example.com', consent: true }, deps()),
    ).toEqual({
      ok: true,
    })
    expect(mail.sent).toHaveLength(1)
  })

  it('makes an unsubscribed address pending again with fresh consent', async () => {
    await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
    await unsubscribeWaitlist(tokenOf(mail.sent[0]), deps())
    advance(DAY)
    await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
    expect(mail.sent).toHaveLength(2)
    const row = await rowFor('sam@example.com')
    expect(row).toMatchObject({
      status: 'pending',
      unsubscribedAt: null,
      emailsSent: 1,
    })
    expect(row.consentedAt).toEqual(clock)
  })

  it('returns ok on a provider failure, logs without the address, and the next join sends', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    mail.fail = true
    expect(
      await joinWaitlist(
        { email: 'secret@example.com', consent: true },
        deps(),
      ),
    ).toEqual({
      ok: true,
    })
    expect(mail.sent).toHaveLength(0)
    expect(String(spy.mock.calls[0][0])).not.toContain('secret@example.com')
    spy.mockRestore()

    mail.fail = false
    expect(
      await joinWaitlist(
        { email: 'secret@example.com', consent: true },
        deps(),
      ),
    ).toEqual({
      ok: true,
    })
    expect(mail.sent).toHaveLength(1)
  })

  it('returns without waiting for the provider', async () => {
    let release: () => void = () => undefined
    const slow: EmailProvider = {
      send: () =>
        new Promise<void>((resolve) => {
          release = resolve
        }),
    }
    const result = await joinRaw(
      { email: 'slow@example.com', consent: true },
      { db, mail: slow, now: () => clock, baseUrl: BASE },
    )
    expect(result).toEqual({ ok: true })
    release()
    await flushPendingSends()
  })
})

describe('confirmWaitlist', () => {
  it('confirms within seven days, is idempotent, and expires after', async () => {
    await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
    const token = tokenOf(mail.sent[0])
    advance(6 * DAY)
    expect(await confirmWaitlist(token, deps())).toBe('confirmed')
    expect(await confirmWaitlist(token, deps())).toBe('already_confirmed')

    await joinWaitlist({ email: 'late@example.com', consent: true }, deps())
    const late = tokenOf(mail.sent[1])
    advance(8 * DAY)
    expect(await confirmWaitlist(late, deps())).toBe('expired')
  })

  it('rejects unknown and unsubscribed tokens', async () => {
    expect(await confirmWaitlist('nope', deps())).toBe('invalid')
    await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
    const token = tokenOf(mail.sent[0])
    await unsubscribeWaitlist(token, deps())
    expect(await confirmWaitlist(token, deps())).toBe('invalid')
  })
})

describe('unsubscribeWaitlist', () => {
  it('works at any age, is idempotent and rejects unknown tokens', async () => {
    await joinWaitlist({ email: 'sam@example.com', consent: true }, deps())
    const token = tokenOf(mail.sent[0])
    await confirmWaitlist(token, deps())
    advance(400 * DAY)
    expect(await unsubscribeWaitlist(token, deps())).toBe('unsubscribed')
    expect(await unsubscribeWaitlist(token, deps())).toBe('unsubscribed')
    expect((await rowFor('sam@example.com')).status).toBe('unsubscribed')
    expect(await unsubscribeWaitlist('unknown', deps())).toBe('invalid')
  })
})

describe('createRateLimiter', () => {
  it('never holds more than its cap of keys', () => {
    let t = 0
    const limiter = createRateLimiter({
      max: 5,
      windowMs: 1000,
      maxKeys: 100,
      now: () => t,
    })
    for (let i = 0; i < 1000; i++) limiter.take(`k${i}`)
    expect(limiter.size()).toBeLessThanOrEqual(100)
    t = 5000
    for (let i = 0; i < 1000; i++) limiter.take(`n${i}`)
    expect(limiter.size()).toBeLessThanOrEqual(100)
  })

  it('blocks the sixth call in a window and recovers after it', () => {
    let t = 0
    const limiter = createRateLimiter({ max: 5, windowMs: 1000, now: () => t })
    for (let i = 0; i < 5; i++) expect(limiter.take('ip')).toBe(true)
    expect(limiter.take('ip')).toBe(false)
    expect(limiter.take('other')).toBe(true)
    t = 1001
    expect(limiter.take('ip')).toBe(true)
  })
})

describe('ResendProvider', () => {
  it('posts to Resend with the key and throws on a failure status', async () => {
    const calls: { url: string; init: RequestInit }[] = []
    const ok = new ResendProvider(
      'key_1',
      'Jobmigo <hello@jobmigo.test>',
      (url, init) => {
        calls.push({ url, init })
        return Promise.resolve(new Response('{}', { status: 200 }))
      },
    )
    await ok.send({
      to: 'a@example.com',
      subject: 's',
      html: '<p>h</p>',
      text: 't',
    })
    expect(calls[0].url).toBe('https://api.resend.com/emails')
    expect(
      (calls[0].init.headers as Record<string, string>).authorization,
    ).toBe('Bearer key_1')
    expect(JSON.parse(String(calls[0].init.body))).toMatchObject({
      from: 'Jobmigo <hello@jobmigo.test>',
      to: ['a@example.com'],
    })
    const bad = new ResendProvider('k', 'f', () =>
      Promise.resolve(new Response('', { status: 422 })),
    )
    await expect(
      bad.send({ to: 'a@example.com', subject: 's', html: 'h', text: 't' }),
    ).rejects.toThrow(/422/)
  })
})
