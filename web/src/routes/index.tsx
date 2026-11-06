import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-4 px-6">
      <p className="text-sm font-extrabold tracking-wide text-accent-strong uppercase">
        Jobmigo
      </p>
      <h1 className="text-4xl leading-tight font-semibold">
        Skip the ghost pipeline. Get the interview.
      </h1>
      <p className="text-lg">
        Scaffold ready. The app shell and sign-in arrive with feature 1.
      </p>
    </main>
  )
}
