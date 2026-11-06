import { Link, createFileRoute, redirect } from '@tanstack/react-router'
import { getSession } from '#/lib/auth.functions'

export const Route = createFileRoute('/')({
  beforeLoad: async () => {
    if (await getSession()) throw redirect({ to: '/dashboard' })
  },
  component: Home,
})

function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-5 px-4 py-10">
      <p className="font-display text-xl font-semibold text-accent-strong">
        Jobmigo
      </p>
      <h1 className="text-4xl leading-tight font-semibold">
        Skip the ghost pipeline. Get the interview.
      </h1>
      <p className="text-lg">
        Your AI job-application assistant. Tailored applications, clear next
        steps.
      </p>
      <div className="flex flex-wrap gap-3">
        <Link
          to="/sign-up"
          className="inline-flex min-h-11 items-center rounded-md bg-accent-strong px-5 font-bold text-white hover:bg-accent-strong-hover"
        >
          Get started
        </Link>
        <Link
          to="/sign-in"
          className="inline-flex min-h-11 items-center rounded-md border border-border-strong bg-surface px-5 font-bold text-ink hover:bg-surface-muted"
        >
          Sign in
        </Link>
      </div>
    </main>
  )
}
