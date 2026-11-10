import {
  Link,
  Outlet,
  createFileRoute,
  redirect,
  useNavigate,
} from '@tanstack/react-router'
import type { ErrorComponentProps } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { authClient } from '#/lib/auth-client'
import { getSession } from '#/lib/auth.functions'

export const Route = createFileRoute('/_app')({
  beforeLoad: async () => {
    const session = await getSession()
    if (!session) throw redirect({ to: '/sign-in' })
    return { user: session.user }
  },
  component: AppShell,
  errorComponent: RouteError,
})

const SOON = ['Jobs', 'Applications', 'Outreach', 'Documents', 'Settings']

const NAV_ITEM =
  'flex min-h-11 items-center justify-between rounded-md px-3 font-bold'

function AppShell() {
  const { user } = Route.useRouteContext()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  async function signOut() {
    await authClient.signOut()
    queryClient.clear()
    await navigate({ to: '/sign-in' })
  }

  return (
    <div className="min-h-screen md:flex">
      <aside className="flex flex-col gap-4 border-b border-border bg-surface p-4 md:w-64 md:shrink-0 md:border-r md:border-b-0">
        <p className="font-display text-2xl font-semibold text-ink">Jobmigo</p>
        <nav aria-label="Main" className="flex flex-col gap-1">
          <Link
            to="/dashboard"
            className={`${NAV_ITEM} text-ink hover:bg-surface-muted`}
            activeProps={{
              className: `${NAV_ITEM} bg-accent-soft text-accent-soft-ink`,
            }}
          >
            Dashboard
          </Link>
          <Link
            to="/profile"
            className={`${NAV_ITEM} text-ink hover:bg-surface-muted`}
            activeProps={{
              className: `${NAV_ITEM} bg-accent-soft text-accent-soft-ink`,
            }}
          >
            Career profile
          </Link>
          {SOON.map((label) => (
            <span
              key={label}
              aria-disabled="true"
              className={`${NAV_ITEM} cursor-not-allowed text-faint`}
            >
              {label}
              <span className="rounded-full bg-neutral-bg px-2 py-0.5 text-xs text-neutral-ink">
                Soon
              </span>
            </span>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-2 border-t border-border pt-4">
          <p className="truncate text-sm text-muted" title={user.email}>
            {user.name}
          </p>
          <button
            type="button"
            onClick={signOut}
            className="min-h-11 rounded-full border border-border-strong bg-surface px-3 font-bold text-ink hover:bg-surface-muted"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  )
}

function RouteError({ error, reset }: ErrorComponentProps) {
  return (
    <div
      role="alert"
      className="m-4 rounded-xl border border-border bg-surface p-6"
    >
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="mt-1 text-muted">
        {error instanceof Error && error.message
          ? error.message
          : 'An unexpected error occurred.'}
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-4 min-h-11 rounded-full bg-accent-strong px-4 font-bold text-white hover:bg-accent-strong-hover"
      >
        Try again
      </button>
    </div>
  )
}
