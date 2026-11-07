import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from '@tanstack/react-router'
import { joinWaitlistFn } from '#/lib/waitlist.functions'

type Errors = { email?: string; consent?: string; form?: string }

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function sourceFromUrl(): string | undefined {
  const params = new URLSearchParams(window.location.search)
  return params.get('utm_source') ?? params.get('ref') ?? undefined
}

export function WaitlistForm() {
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const emailRef = useRef<HTMLInputElement>(null)
  const consentRef = useRef<HTMLInputElement>(null)

  function fail(next: Errors) {
    setErrors(next)
    if (next.email) emailRef.current?.focus()
    else if (next.consent) consentRef.current?.focus()
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const email = String(data.get('email') ?? '').trim()
    const consent = data.get('consent') === 'on'
    const website = String(data.get('website') ?? '')

    const next: Errors = {}
    if (!EMAIL_PATTERN.test(email)) next.email = 'Enter a valid email address.'
    if (!consent) next.consent = 'Please tick the box so we can email you.'
    if (Object.keys(next).length) return fail(next)

    setErrors({})
    setBusy(true)
    try {
      const result = await joinWaitlistFn({
        data: { email, consent, website, source: sourceFromUrl() },
      })
      if (result.ok) setDone(true)
      else if (result.code === 'invalid_email') fail({ email: result.message })
      else if (result.code === 'consent_required')
        fail({ consent: result.message })
      else fail({ form: result.message })
    } catch {
      fail({
        form: 'Could not reach the server. Check your connection and try again.',
      })
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="rounded-xl border border-good-ink/30 bg-good-bg p-5 text-good-ink"
      >
        <p className="text-lg font-bold">Check your inbox to confirm</p>
        <p className="mt-1 text-sm">
          We sent you a link. Once you confirm, you are on the list. If it does
          not arrive in a few minutes, check your spam folder.
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <div role="alert" aria-live="polite" className="empty:hidden">
        {errors.form && (
          <p className="rounded-md bg-bad-bg px-3 py-2 text-sm font-semibold text-bad-ink">
            {errors.form}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="waitlist-email" className="text-sm font-bold text-ink">
          Email address
        </label>
        <input
          ref={emailRef}
          id="waitlist-email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@email.com"
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? 'waitlist-email-error' : undefined}
          className="min-h-12 w-full rounded-md border-2 border-ink bg-surface px-4 text-base text-ink aria-[invalid=true]:border-alert"
        />
        {errors.email && (
          <p
            id="waitlist-email-error"
            className="text-sm font-semibold text-alert"
          >
            {errors.email}
          </p>
        )}
      </div>

      {/* Honeypot: people never see or reach this field; bots tend to fill it. */}
      <div
        aria-hidden="true"
        className="absolute -left-[9999px] h-0 w-0 overflow-hidden"
      >
        <label htmlFor="waitlist-website">Website</label>
        <input
          id="waitlist-website"
          name="website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex items-start gap-3">
          <input
            ref={consentRef}
            id="waitlist-consent"
            name="consent"
            type="checkbox"
            aria-invalid={Boolean(errors.consent)}
            aria-describedby={
              errors.consent ? 'waitlist-consent-error' : undefined
            }
            className="mt-1 size-5 shrink-0 accent-accent-strong"
          />
          <label
            htmlFor="waitlist-consent"
            className="text-sm leading-relaxed text-body"
          >
            Email me about Jobmigo early access and launch updates. I can
            unsubscribe at any time.{' '}
            <Link
              to="/privacy"
              className="font-bold text-accent-strong underline"
            >
              Privacy notice
            </Link>
          </label>
        </div>
        {errors.consent && (
          <p
            id="waitlist-consent-error"
            className="text-sm font-semibold text-alert"
          >
            {errors.consent}
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={busy}
        className="min-h-12 rounded-md bg-ink px-6 text-base font-bold text-white transition-colors hover:bg-body disabled:opacity-70"
      >
        {busy ? 'Joining…' : 'Join the waitlist'}
      </button>
    </form>
  )
}
