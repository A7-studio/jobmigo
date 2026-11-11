import { useEffect } from 'react'
import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { BTN, BTN_PRIMARY, Problem } from '#/components/cv/parts'
import { useMe } from '#/lib/useMe'
import { useSignOut } from '#/lib/use-sign-out'

export const Route = createFileRoute('/_app/settings')({
  head: () => ({ meta: [{ title: 'Settings | Jobmigo' }] }),
  component: Settings,
})

const CARD = 'rounded-2xl border border-border bg-surface p-5'

/** What is not part of this version. Nothing here is switched on, so nothing is a button. */
const LATER = [
  {
    title: 'Your data',
    body: 'Export your data, or delete your account.',
  },
  { title: 'Plan and billing', body: 'Plans, payments and invoices.' },
  { title: 'Telegram', body: 'Daily digest and alerts in Telegram.' },
]

function Settings() {
  const me = useMe()
  const navigate = useNavigate()
  const signOut = useSignOut()
  const unauthorized = me.data?.ok === false && me.data.code === 'unauthorized'

  useEffect(() => {
    if (unauthorized) void navigate({ to: '/sign-in' })
  }, [unauthorized, navigate])

  if (me.isPending || unauthorized) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading Settings"
        className="mx-auto max-w-[720px] animate-pulse"
      >
        <div className="h-9 w-1/3 rounded-md bg-surface-sunken" />
        <div className="mt-6 h-40 rounded-2xl bg-surface-sunken" />
      </div>
    )
  }

  const result = me.data
  if (me.isError || !result?.ok) {
    const failure =
      result?.ok === false ? result.message : 'Could not reach the server.'
    return (
      <div className="mx-auto max-w-[720px]">
        <Problem title="We could not load Settings" body={failure}>
          <button
            type="button"
            className={BTN_PRIMARY}
            disabled={me.isFetching}
            onClick={() => void me.refetch()}
          >
            {me.isFetching ? 'Retrying…' : 'Retry'}
          </button>
        </Problem>
      </div>
    )
  }

  const name = result.me.displayName ?? result.me.email

  return (
    <div className="mx-auto flex w-full max-w-[720px] flex-col gap-6">
      <header>
        <h1 className="font-display text-[28px] font-bold tracking-tight text-ink">
          Settings
        </h1>
        <p className="mt-1.5 text-sm text-faint">Your account.</p>
      </header>

      <section aria-labelledby="account" className={CARD}>
        <h2 id="account" className="font-display text-lg font-bold text-ink">
          Account
        </h2>
        <dl className="mt-3 flex flex-col gap-3">
          <div>
            <dt className="text-xs font-bold text-faint">Name</dt>
            <dd className="break-words text-[15px] text-ink">{name}</dd>
          </div>
          <div>
            <dt className="text-xs font-bold text-faint">Email</dt>
            <dd className="break-words text-[15px] text-ink">
              {result.me.email}
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="session" className={CARD}>
        <h2 id="session" className="font-display text-lg font-bold text-ink">
          Sign out
        </h2>
        <p className="mt-1 text-sm text-muted">Signed in as {name}.</p>
        <button
          type="button"
          className={`${BTN} mt-3`}
          onClick={() => void signOut()}
        >
          Sign out
        </button>
      </section>

      {result.me.staff?.permissions.includes('overview.read') ? (
        <section aria-labelledby="staff" className={CARD}>
          <h2 id="staff" className="font-display text-lg font-bold text-ink">
            Staff
          </h2>
          <p className="mt-1 text-sm text-muted">
            What the AI calls cost and how well they went.
          </p>
          <Link to="/admin/ai" className={`${BTN} mt-3`}>
            AI cost and quality
          </Link>
        </section>
      ) : null}

      <section aria-labelledby="later" className={CARD}>
        <h2 id="later" className="font-display text-lg font-bold text-ink">
          Later
        </h2>
        <p className="mt-1 text-sm text-muted">
          Not part of this version. Nothing here is switched on.
        </p>
        <ul className="mt-3 flex flex-col">
          {LATER.map((item) => (
            <li
              key={item.title}
              className="flex items-center justify-between gap-3 border-t border-surface-sunken py-3 first:border-t-0"
            >
              <div className="min-w-0">
                <p className="text-[15px] font-bold text-ink">{item.title}</p>
                <p className="text-[13px] text-muted">{item.body}</p>
              </div>
              <span className="shrink-0 rounded-full bg-neutral-bg px-2.5 py-1 text-xs font-bold text-neutral-ink">
                Later
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
