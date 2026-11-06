import { useEffect } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { ApiError } from '#/lib/api'
import { useMe } from '#/lib/useMe'

export const Route = createFileRoute('/_app/dashboard')({
  component: Dashboard,
})

function Dashboard() {
  const me = useMe()
  const navigate = useNavigate()
  const unauthorized = me.error instanceof ApiError && me.error.status === 401

  useEffect(() => {
    if (unauthorized) void navigate({ to: '/sign-in' })
  }, [unauthorized, navigate])

  if (me.isPending || unauthorized) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading your dashboard"
        className="max-w-xl animate-pulse"
      >
        <div className="h-9 w-2/3 rounded-md bg-surface-sunken" />
        <div className="mt-4 h-24 rounded-xl bg-surface-sunken" />
      </div>
    )
  }

  if (me.isError) {
    return (
      <div
        role="alert"
        className="max-w-xl rounded-xl border border-border bg-surface p-6"
      >
        <h1 className="text-xl font-semibold">
          We could not load your dashboard
        </h1>
        <p className="mt-1 text-muted">{me.error.message}</p>
        <button
          type="button"
          onClick={() => void me.refetch()}
          disabled={me.isFetching}
          className="mt-4 min-h-11 rounded-md bg-accent-strong px-4 font-bold text-white hover:bg-accent-strong-hover disabled:opacity-70"
        >
          {me.isFetching ? 'Retrying…' : 'Retry'}
        </button>
      </div>
    )
  }

  const name = me.data.display_name ?? me.data.email

  return (
    <div className="max-w-xl">
      <h1 className="text-3xl font-semibold">Hi, {name}</h1>
      <div className="mt-6 flex items-center gap-4 rounded-xl border border-border bg-surface p-6">
        <div
          aria-hidden="true"
          className="grid size-14 shrink-0 place-items-center rounded-full bg-accent font-display text-2xl font-semibold text-accent-ink"
        >
          M
        </div>
        <div>
          <h2 className="text-lg font-semibold">Migo is getting ready</h2>
          <p className="text-muted">
            Your jobs, applications and next steps will show up here soon.
          </p>
        </div>
      </div>
    </div>
  )
}
