import { z } from 'zod'
import { createRateLimiter } from './rate-limit'
import type { RateLimiter } from './rate-limit'
import { joinWaitlist } from './waitlist'
import type { JoinResult, WaitlistDeps } from './waitlist'

export const joinInputSchema = z.object({
  email: z.string().max(2000),
  consent: z.boolean(),
  source: z.string().max(2000).optional(),
  website: z.string().max(2000).optional(),
})

export type JoinInputPayload = z.infer<typeof joinInputSchema>

export type JoinApiResult =
  JoinResult | { ok: false; code: 'rate_limited'; message: string }

const joinLimiter = createRateLimiter({ max: 5, windowMs: 10 * 60 * 1000 })
const globalLimiter = createRateLimiter({ max: 60, windowMs: 10 * 60 * 1000 })

/**
 * The caller's address, for rate limiting only. `cf-connecting-ip` is trusted only
 * when TRUST_PROXY_HEADERS is `true`, which must be set only behind Cloudflare and
 * Caddy (feature 28b), where the header cannot be set by the client. Otherwise there
 * is no trustworthy address and `null` is returned; `x-forwarded-for` is never used.
 */
export function clientIp(
  headers: Headers,
  trustProxy: boolean = process.env.TRUST_PROXY_HEADERS === 'true',
): string | null {
  if (!trustProxy) return null
  return headers.get('cf-connecting-ip')?.trim() || null
}

export async function handleJoin(
  input: JoinInputPayload,
  headers: Headers,
  options: {
    limiter?: RateLimiter
    globalLimiter?: RateLimiter
    trustProxy?: boolean
    deps?: WaitlistDeps
  } = {},
): Promise<JoinApiResult> {
  // A bot filled the hidden field: look successful, store and send nothing.
  if (input.website?.trim()) return { ok: true }

  const limited: JoinApiResult = {
    ok: false,
    code: 'rate_limited',
    message: 'Too many attempts. Please try again in a few minutes.',
  }
  // A flood cap across everyone, so abuse cannot use the sender domain freely.
  if (!(options.globalLimiter ?? globalLimiter).take('all')) return limited
  const ip = clientIp(headers, options.trustProxy)
  if (ip && !(options.limiter ?? joinLimiter).take(ip)) return limited

  return joinWaitlist(
    { email: input.email, consent: input.consent, source: input.source },
    options.deps,
  )
}
