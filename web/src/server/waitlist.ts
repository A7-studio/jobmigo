import { createHash, randomBytes } from 'node:crypto'
import { eq } from 'drizzle-orm'
import { z } from 'zod'
import { getDb } from './db/client'
import type { Db } from './db/client'
import { waitlistSignup } from './db/schema'
import { logger } from './logger'
import { getEmailProvider } from './mail'
import type { EmailProvider } from './mail'

export const CONSENT_TEXT_VERSION = 'waitlist-v1'
const RESEND_AFTER_MS = 10 * 60 * 1000
const CONFIRM_VALID_MS = 7 * 24 * 60 * 60 * 1000
const MAX_EMAILS = 5

export type WaitlistDeps = {
  db?: Db
  mail?: EmailProvider
  now?: () => Date
  baseUrl?: string
}

export type JoinInput = {
  email: string
  consent: boolean
  source?: string | null
}

export type JoinResult =
  | { ok: true }
  | {
      ok: false
      code: 'invalid_email' | 'consent_required'
      message: string
    }

export type ConfirmState =
  'confirmed' | 'already_confirmed' | 'expired' | 'invalid'

const emailSchema = z.string().trim().toLowerCase().max(254).pipe(z.email())
const SOURCE_PATTERN = /^[a-z0-9_.-]{1,64}$/

function resolve(deps: WaitlistDeps) {
  return {
    db: deps.db ?? getDb(),
    mail: deps.mail ?? getEmailProvider(),
    now: deps.now ?? (() => new Date()),
    baseUrl: (
      deps.baseUrl ??
      process.env.PUBLIC_URL ??
      process.env.BETTER_AUTH_URL ??
      ''
    ).replace(/\/$/, ''),
  }
}

export function hashToken(token: string): string {
  return createHash('sha256').update(token).digest('hex')
}

function newToken(): { raw: string; hash: string } {
  const raw = randomBytes(32).toString('base64url')
  return { raw, hash: hashToken(raw) }
}

function cleanSource(source: string | null | undefined): string | null {
  const value = source?.trim().toLowerCase()
  return value && SOURCE_PATTERN.test(value) ? value : null
}

export function confirmationEmail(baseUrl: string, token: string) {
  const confirm = `${baseUrl}/waitlist/confirm?token=${token}`
  const unsubscribe = `${baseUrl}/waitlist/unsubscribe?token=${token}`
  const subject = 'Confirm your spot on the Jobmigo waitlist'
  const text = [
    'Hi,',
    '',
    'Thanks for joining the Jobmigo waitlist. Please confirm your email so we can keep you posted on early access:',
    '',
    confirm,
    '',
    'If you did not sign up, ignore this email and nothing will happen.',
    '',
    `Unsubscribe: ${unsubscribe}`,
    '',
    'Jobmigo, a product of A7Studio',
  ].join('\n')
  const html = `<!doctype html><html><body style="margin:0;background:#FAF9F5;font-family:Arial,Helvetica,sans-serif;color:#1A1A18"><div style="max-width:520px;margin:0 auto;padding:32px 20px"><p style="font-size:22px;font-weight:700;margin:0 0 20px">job<span style="color:#B04A27">migo</span></p><p style="font-size:16px;line-height:1.6">Thanks for joining the Jobmigo waitlist. Please confirm your email so we can keep you posted on early access.</p><p style="margin:24px 0"><a href="${confirm}" style="background:#B04A27;color:#ffffff;text-decoration:none;font-weight:700;padding:14px 24px;border-radius:12px;display:inline-block">Confirm my email</a></p><p style="font-size:14px;line-height:1.6;color:#4A4944">If you did not sign up, ignore this email and nothing will happen.</p><p style="font-size:12px;color:#5E5D59">Jobmigo, a product of A7Studio. <a href="${unsubscribe}" style="color:#5E5D59">Unsubscribe</a></p></div></body></html>`
  return {
    subject,
    text,
    html,
    headers: { 'List-Unsubscribe': `<${unsubscribe}>` },
  }
}

export async function joinWaitlist(
  input: JoinInput,
  deps: WaitlistDeps = {},
): Promise<JoinResult> {
  const { db, mail, now, baseUrl } = resolve(deps)

  const parsed = emailSchema.safeParse(input.email)
  if (!parsed.success) {
    return {
      ok: false,
      code: 'invalid_email',
      message: 'Enter a valid email address.',
    }
  }
  if (!input.consent) {
    return {
      ok: false,
      code: 'consent_required',
      message: 'Please tick the box so we can email you.',
    }
  }
  const email = parsed.data
  const source = cleanSource(input.source)
  const time = now()
  const token = newToken()

  let rowId: string
  let send = false

  const inserted = await db
    .insert(waitlistSignup)
    .values({
      email,
      consentTextVersion: CONSENT_TEXT_VERSION,
      consentedAt: time,
      source,
      tokenHash: token.hash,
      tokenSentAt: time,
    })
    .onConflictDoNothing()
    .returning({ id: waitlistSignup.id })

  const created = inserted.at(0)
  if (created) {
    rowId = created.id
    send = true
  } else {
    const rows = await db
      .select()
      .from(waitlistSignup)
      .where(eq(waitlistSignup.email, email))
    const row = rows.at(0)
    if (!row) return { ok: true } // deleted between the two statements; nothing to do
    rowId = row.id
    if (row.status === 'unsubscribed') {
      await db
        .update(waitlistSignup)
        .set({
          status: 'pending',
          consentTextVersion: CONSENT_TEXT_VERSION,
          consentedAt: time,
          source: source ?? row.source,
          tokenHash: token.hash,
          tokenSentAt: time,
          emailsSent: 1,
          confirmedAt: null,
          unsubscribedAt: null,
          updatedAt: time,
        })
        .where(eq(waitlistSignup.id, row.id))
      send = true
    } else if (
      row.status === 'pending' &&
      time.getTime() - row.tokenSentAt.getTime() >= RESEND_AFTER_MS &&
      row.emailsSent < MAX_EMAILS
    ) {
      await db
        .update(waitlistSignup)
        .set({
          tokenHash: token.hash,
          tokenSentAt: time,
          emailsSent: row.emailsSent + 1,
          updatedAt: time,
        })
        .where(eq(waitlistSignup.id, row.id))
      send = true
    }
  }

  if (send) {
    // Sending runs in the background so every path costs the same to the caller.
    track(
      sendConfirmation({
        db,
        mail,
        rowId,
        email,
        baseUrl,
        token: token.raw,
        time,
      }),
    )
  }
  return { ok: true }
}

const pendingSends = new Set<Promise<void>>()

function track(task: Promise<void>) {
  pendingSends.add(task)
  void task.finally(() => pendingSends.delete(task))
}

/** Wait for background sends to finish (tests, graceful shutdown). */
export async function flushPendingSends(): Promise<void> {
  await Promise.all([...pendingSends])
}

async function sendConfirmation(args: {
  db: Db
  mail: EmailProvider
  rowId: string
  email: string
  baseUrl: string
  token: string
  time: Date
}): Promise<void> {
  try {
    await args.mail.send({
      to: args.email,
      ...confirmationEmail(args.baseUrl, args.token),
    })
  } catch (error) {
    logger.error('waitlist email failed', {
      error: error instanceof Error ? error.name : typeof error,
    })
    // Let the next attempt send again at once.
    await args.db
      .update(waitlistSignup)
      .set({ tokenSentAt: new Date(0), updatedAt: args.time })
      .where(eq(waitlistSignup.id, args.rowId))
      .catch(() => undefined)
  }
}

export async function confirmWaitlist(
  token: string,
  deps: WaitlistDeps = {},
): Promise<ConfirmState> {
  const { db, now } = resolve(deps)
  const rows = await db
    .select()
    .from(waitlistSignup)
    .where(eq(waitlistSignup.tokenHash, hashToken(token)))
  const row = rows.at(0)
  if (!row || row.status === 'unsubscribed') return 'invalid'
  if (row.status === 'confirmed') return 'already_confirmed'
  const time = now()
  if (time.getTime() - row.tokenSentAt.getTime() > CONFIRM_VALID_MS)
    return 'expired'
  await db
    .update(waitlistSignup)
    .set({ status: 'confirmed', confirmedAt: time, updatedAt: time })
    .where(eq(waitlistSignup.id, row.id))
  return 'confirmed'
}

export async function unsubscribeWaitlist(
  token: string,
  deps: WaitlistDeps = {},
): Promise<'unsubscribed' | 'invalid'> {
  const { db, now } = resolve(deps)
  const rows = await db
    .select()
    .from(waitlistSignup)
    .where(eq(waitlistSignup.tokenHash, hashToken(token)))
  const row = rows.at(0)
  if (!row) return 'invalid'
  if (row.status !== 'unsubscribed') {
    const time = now()
    await db
      .update(waitlistSignup)
      .set({ status: 'unsubscribed', unsubscribedAt: time, updatedAt: time })
      .where(eq(waitlistSignup.id, row.id))
  }
  return 'unsubscribed'
}
