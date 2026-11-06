import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { authClient } from '#/lib/auth-client'

type Mode = 'sign-in' | 'sign-up'
type Errors = {
  name?: string
  email?: string
  password?: string
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
    title: 'Create your account',
    lead: 'Get your applications out of the ghost pipeline.',
    submit: 'Create account',
    busy: 'Creating account…',
    google: 'Sign up with Google',
    switchText: 'Already have an account?',
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

  function fail(next: Errors) {
    setErrors(next)
    if (next.name) nameRef.current?.focus()
    else if (next.email) emailRef.current?.focus()
    else if (next.password) passwordRef.current?.focus()
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
      await navigate({ to: '/dashboard' })
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
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-6 px-4 py-10">
      <Link to="/" className="font-display text-2xl font-semibold text-ink">
        Jobmigo
      </Link>
      <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
        <h1 className="text-2xl font-semibold">{copy.title}</h1>
        <p className="mt-1 text-muted">{copy.lead}</p>

        <div role="alert" aria-live="polite" className="mt-4 empty:hidden">
          {errors.form && (
            <p className="rounded-md bg-bad-bg px-3 py-2 text-sm font-semibold text-bad-ink">
              {errors.form}
            </p>
          )}
        </div>

        <form
          onSubmit={onSubmit}
          noValidate
          className="mt-4 flex flex-col gap-4"
        >
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
            hint={mode === 'sign-up' ? 'At least 8 characters.' : undefined}
          >
            <input
              ref={passwordRef}
              id="password"
              name="password"
              type="password"
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
          <button
            type="submit"
            disabled={busy}
            className="min-h-11 rounded-md bg-accent-strong px-4 font-bold text-white transition-colors hover:bg-accent-strong-hover disabled:opacity-70"
          >
            {busy ? copy.busy : copy.submit}
          </button>
        </form>

        {google && (
          <button
            type="button"
            onClick={onGoogle}
            disabled={busy}
            className="mt-3 min-h-11 w-full rounded-md border border-border-strong bg-surface px-4 font-bold text-ink hover:bg-surface-muted disabled:opacity-70"
          >
            {copy.google}
          </button>
        )}

        <p className="mt-6 text-sm text-muted">
          {copy.switchText}{' '}
          <Link
            to={copy.switchTo}
            className="font-bold text-accent-strong underline"
          >
            {copy.switchLink}
          </Link>
        </p>
      </div>
    </main>
  )
}

const INPUT =
  'min-h-11 w-full rounded-md border border-border-strong bg-surface px-3 text-ink aria-[invalid=true]:border-alert'

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
      <label htmlFor={id} className="text-sm font-bold text-ink">
        {label}
      </label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-faint">
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
