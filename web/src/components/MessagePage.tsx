import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

export function MessagePage({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-6 px-4 py-10">
      <Link to="/" className="font-display text-2xl font-semibold text-ink">
        job<span className="text-accent-strong">migo</span>
      </Link>
      <div
        role="status"
        aria-live="polite"
        className="rounded-xl border border-border bg-surface p-6 shadow-sm"
      >
        <h1 className="text-2xl font-semibold">{title}</h1>
        <div className="mt-2 flex flex-col gap-4 text-muted">{children}</div>
      </div>
    </main>
  )
}

export const LINK_BUTTON =
  'inline-flex min-h-11 items-center justify-center rounded-full bg-accent-strong px-5 font-bold text-white hover:bg-accent-strong-hover'
