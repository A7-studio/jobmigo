import { Link, Outlet, createFileRoute, redirect } from '@tanstack/react-router'
import type { ErrorComponentProps } from '@tanstack/react-router'
import { getSession } from '#/lib/auth.functions'
import { NAV_ITEMS } from '#/lib/app-nav'
import { useSignOut } from '#/lib/use-sign-out'

export const Route = createFileRoute('/_app')({
  beforeLoad: async () => {
    const session = await getSession()
    if (!session) throw redirect({ to: '/sign-in' })
    return { user: session.user }
  },
  component: AppShell,
  errorComponent: RouteError,
})

// Each place: a row in the sidebar, a tab in the bottom bar on phones.
const NAV_ITEM =
  'flex min-h-11 items-center gap-3 rounded-md px-3 font-bold max-md:min-h-14 max-md:flex-1 max-md:flex-col max-md:justify-center max-md:gap-0.5 max-md:px-1 max-md:text-xs'

const ICONS: Record<(typeof NAV_ITEMS)[number]['label'], React.ReactNode> = {
  Today: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />,
  Jobs: (
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
    </>
  ),
  Profile: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>
  ),
  Settings: (
    <>
      <path d="M4 6h9m4 0h3M4 12h3m4 0h9M4 18h11m4 0h1" />
      <circle cx="15" cy="6" r="2" />
      <circle cx="9" cy="12" r="2" />
      <circle cx="17" cy="18" r="2" />
    </>
  ),
}

function NavIcon({ label }: { label: keyof typeof ICONS }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[label]}
    </svg>
  )
}

function AppShell() {
  const { user } = Route.useRouteContext()
  const signOut = useSignOut()

  return (
    <div className="min-h-screen md:flex">
      <aside className="flex items-center justify-between gap-4 border-b border-border bg-surface p-4 md:w-64 md:shrink-0 md:flex-col md:items-stretch md:justify-start md:border-r md:border-b-0">
        <p className="font-display text-2xl font-semibold text-ink">Jobmigo</p>
        <nav
          aria-label="Main"
          className="flex flex-col gap-1 max-md:fixed max-md:inset-x-0 max-md:bottom-0 max-md:z-40 max-md:flex-row max-md:border-t max-md:border-border max-md:bg-surface max-md:px-2 max-md:pt-1.5 max-md:pb-[calc(0.375rem+env(safe-area-inset-bottom))]"
        >
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`${NAV_ITEM} text-ink hover:bg-surface-muted`}
              activeProps={{
                className: `${NAV_ITEM} bg-accent-soft text-accent-soft-ink`,
              }}
            >
              <NavIcon label={item.label} />
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2 md:mt-auto md:flex-col md:items-stretch md:border-t md:border-border md:pt-4">
          <p
            className="truncate text-sm text-muted max-md:hidden"
            title={user.email}
          >
            {user.name}
          </p>
          <button
            type="button"
            onClick={() => void signOut()}
            className="min-h-11 rounded-full border border-border-strong bg-surface px-3 font-bold text-ink hover:bg-surface-muted"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 max-md:pb-24 md:p-8">
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
