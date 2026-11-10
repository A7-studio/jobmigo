import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { authClient } from '#/lib/auth-client'
import { AuthShell } from './AuthShell'

type Mode = 'sign-in' | 'sign-up'
type Errors = {
  name?: string
  email?: string
  password?: string
  consent?: string
  form?: string
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const COPY = {
  'sign-in': {
    title: 'Welcome back',
    lead: 'Sign in to pick up where you left off.',
    submit: 'Sign in',
    busy: 'Signing in…',
    google: 'Continue with Google',
    switchText: 'New to Jobmigo?',
    switchLink: 'Create an account',
    switchTo: '/sign-up',
  },
  'sign-up': {
    title: 'Let’s make job hunting feel lighter.',
    lead: 'Create your free account. It takes under a minute.',
    submit: 'Create my free account',
    busy: 'Creating account…',
    google: 'Continue with Google',
    switchText: 'No card needed. Already have an account?',
    switchLink: 'Sign in',
    switchTo: '/sign-in',
  },
} as const

function serverMessage(code: string | undefined, mode: Mode): Errors {
  switch (code) {
    case 'INVALID_EMAIL_OR_PASSWORD':
      return {
        form: 'That email and password do not match. Check them and try again.',
      }
    case 'USER_ALREADY_EXISTS':
    case 'USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL':
      return {
        form: 'An account with this email already exists. Try signing in instead.',
      }
    case 'INVALID_EMAIL':
      return { email: 'Enter a valid email address.' }
    case 'PASSWORD_TOO_SHORT':
      return { password: 'Use at least 8 characters.' }
    default:
      return {
        form:
          mode === 'sign-in'
            ? 'We could not sign you in. Please try again.'
            : 'We could not create your account. Please try again.',
      }
  }
}

export function AuthForm({ mode, google }: { mode: Mode; google: boolean }) {
  const copy = COPY[mode]
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)
  const nameRef = useRef<HTMLInputElement>(null)
  const emailRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const consentRef = useRef<HTMLInputElement>(null)

  function fail(next: Errors) {
    setErrors(next)
    if (next.name) nameRef.current?.focus()
    else if (next.email) emailRef.current?.focus()
    else if (next.password) passwordRef.current?.focus()
    else if (next.consent) consentRef.current?.focus()
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const name = String(data.get('name') ?? '').trim()
    const email = String(data.get('email') ?? '').trim()
    const password = String(data.get('password') ?? '')

    const next: Errors = {}
    if (mode === 'sign-up' && !name) next.name = 'Enter your name.'
    if (!EMAIL_PATTERN.test(email)) next.email = 'Enter a valid email address.'
    if (mode === 'sign-up' ? password.length < 8 : !password) {
      next.password =
        mode === 'sign-up'
          ? 'Use at least 8 characters.'
          : 'Enter your password.'
    }
    if (mode === 'sign-up' && data.get('consent') !== 'on') {
      next.consent = 'Agree to the Privacy Policy to create your account.'
    }
    if (Object.keys(next).length) return fail(next)

    setErrors({})
    setBusy(true)
    try {
      const { error } =
        mode === 'sign-up'
          ? await authClient.signUp.email({ name, email, password })
          : await authClient.signIn.email({ email, password })
      if (error) return fail(serverMessage(error.code, mode))
      queryClient.clear()
      await navigate({ to: mode === 'sign-up' ? '/onboarding' : '/dashboard' })
    } catch {
      fail({
        form: 'Could not reach the server. Check your connection and try again.',
      })
    } finally {
      setBusy(false)
    }
  }

  async function onGoogle() {
    setBusy(true)
    await authClient.signIn.social({
      provider: 'google',
      callbackURL: '/dashboard',
    })
    setBusy(false)
  }

  return (
    <AuthShell mode={mode}>
      <div>
        <h1 className="text-4xl leading-[1.1] font-bold sm:text-[42px]">
          {copy.title}
        </h1>
        <p className="mt-3 text-[17px] leading-normal text-muted">
          {copy.lead}
        </p>
      </div>

      <div role="alert" aria-live="polite" className="empty:hidden">
        {errors.form && (
          <p className="rounded-md bg-bad-bg px-3 py-2 text-sm font-semibold text-bad-ink">
            {errors.form}
          </p>
        )}
      </div>

      {google && (
        <>
          <button
            type="button"
            onClick={onGoogle}
            disabled={busy}
            className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-full border border-border-strong bg-surface px-5 text-[15px] font-bold text-ink hover:bg-surface-muted disabled:opacity-70"
          >
            <span aria-hidden="true" className="font-display text-lg font-bold">
              G
            </span>
            {copy.google}
          </button>
          <div className="flex items-center gap-3 text-[13px] text-faint">
            <span className="h-px flex-1 bg-border" />
            or use your email
            <span className="h-px flex-1 bg-border" />
          </div>
        </>
      )}

      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {mode === 'sign-up' && (
          <Field id="name" label="Name" error={errors.name}>
            <input
              ref={nameRef}
              id="name"
              name="name"
              autoComplete="name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'name-error' : undefined}
              className={INPUT}
            />
          </Field>
        )}
        <Field id="email" label="Email" error={errors.email}>
          <input
            ref={emailRef}
            id="email"
            name="email"
            type="email"
            placeholder="you@email.com"
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'email-error' : undefined}
            className={INPUT}
          />
        </Field>
        <Field
          id="password"
          label="Password"
          error={errors.password}
          hint={
            mode === 'sign-up'
              ? 'Use a phrase you will remember. Longer is stronger.'
              : undefined
          }
        >
          <input
            ref={passwordRef}
            id="password"
            name="password"
            type="password"
            placeholder={
              mode === 'sign-up' ? 'At least 8 characters' : undefined
            }
            autoComplete={
              mode === 'sign-up' ? 'new-password' : 'current-password'
            }
            aria-invalid={Boolean(errors.password)}
            aria-describedby={
              [
                errors.password ? 'password-error' : null,
                mode === 'sign-up' ? 'password-hint' : null,
              ]
                .filter(Boolean)
                .join(' ') || undefined
            }
            className={INPUT}
          />
        </Field>
        {mode === 'sign-up' && (
          <div className="flex flex-col gap-1">
            <label
              htmlFor="consent"
              className="flex min-h-11 items-start gap-2.5 text-[13px] leading-normal text-muted"
            >
              <input
                ref={consentRef}
                id="consent"
                name="consent"
                type="checkbox"
                aria-invalid={Boolean(errors.consent)}
                aria-describedby={errors.consent ? 'consent-error' : undefined}
                className="mt-px size-5 shrink-0 accent-accent-strong"
              />
              <span>
                I agree to the{' '}
                <a
                  href="/privacy"
                  target="_blank"
                  rel="noreferrer"
                  className="font-bold text-accent-strong"
                >
                  Privacy Policy
                </a>
                .
              </span>
            </label>
            {errors.consent && (
              <p
                id="consent-error"
                className="text-sm font-semibold text-alert"
              >
                {errors.consent}
              </p>
            )}
          </div>
        )}
        <button
          type="submit"
          disabled={busy}
          className="min-h-12 w-full rounded-full bg-accent-strong px-5 text-base font-bold text-white transition-colors hover:bg-accent-strong-hover disabled:opacity-70"
        >
          {busy ? copy.busy : copy.submit}
        </button>
      </form>

      <p className="text-[13px] leading-normal text-faint">
        {copy.switchText}{' '}
        <Link to={copy.switchTo} className="font-bold text-accent-strong">
          {copy.switchLink}
        </Link>
      </p>
    </AuthShell>
  )
}

const INPUT =
  'min-h-12 w-full rounded-md border-[1.5px] border-border-strong bg-surface px-3.5 text-base text-ink aria-[invalid=true]:border-alert'

function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string
  label: string
  error?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-bold text-muted">
        {label}
      </label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="text-xs font-medium text-faint">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm font-semibold text-alert">
          {error}
        </p>
      )}
    </div>
  )
}
