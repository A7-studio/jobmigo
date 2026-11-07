import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { Migo, Wordmark } from '#/components/Migo'

type Mode = 'sign-in' | 'sign-up'

const NEXT_STEPS = [
  { title: 'Upload your CV', note: 'About a minute. Migo reads it for you.' },
  {
    title: 'Tell Migo what you want',
    note: 'Roles, pay and dealbreakers. Change them any time.',
  },
  {
    title: 'See your first evaluation',
    note: 'Paste a job and see how it fits, with evidence.',
  },
]

const ICON = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

const TRUST = [
  {
    text: 'Your CV is private. Only you can see it.',
    path: 'M6 11h12v9H6zM8 11V8a4 4 0 018 0v3',
  },
  {
    text: 'Nothing is ever sent without your say-so.',
    path: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
  },
  {
    text: 'Export or delete your data whenever you like.',
    path: 'M5 12l5 5 9-10',
  },
]

const BUBBLE = {
  'sign-up': 'Welcome! You are in good hands. I will keep this simple.',
  'sign-in': 'Welcome back! Let’s pick up where you left off.',
} as const

/** Split layout from the Signup design board: form on the left, Migo and reassurance on the right. */
export function AuthShell({
  mode,
  children,
}: {
  mode: Mode
  children: ReactNode
}) {
  return (
    <div className="flex min-h-screen flex-wrap bg-surface">
      <main className="flex min-w-0 flex-[1_1_520px] flex-col justify-center gap-6 px-6 py-8 sm:px-14 sm:pb-12">
        <Link to="/" aria-label="Jobmigo home" className="self-start">
          <Wordmark />
        </Link>
        <div className="flex max-w-[440px] flex-col gap-5">{children}</div>
      </main>
      <aside className="flex min-w-0 flex-[1_1_440px] flex-col justify-center gap-8 bg-accent-soft px-6 py-10 sm:p-14">
        <div className="flex items-end gap-4">
          <Migo size={110} joy label="Migo, the Jobmigo mascot" />
          <p className="max-w-[280px] rounded-[18px_18px_18px_4px] border border-accent-light bg-surface px-[18px] py-3.5 text-base leading-normal text-body">
            {BUBBLE[mode]}
          </p>
        </div>
        {mode === 'sign-up' && (
          <section
            aria-labelledby="next-h"
            className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-6"
          >
            <h2 id="next-h" className="text-xl font-semibold">
              What happens next
            </h2>
            <ol className="flex flex-col gap-4">
              {NEXT_STEPS.map((step, index) => (
                <li key={step.title} className="flex items-start gap-3.5">
                  <span className="grid size-[34px] shrink-0 place-items-center rounded-full bg-accent font-display font-bold text-accent-ink">
                    {index + 1}
                  </span>
                  <span className="text-[15px] leading-normal">
                    <strong className="block text-ink">{step.title}</strong>
                    <span className="text-muted">{step.note}</span>
                  </span>
                </li>
              ))}
            </ol>
          </section>
        )}
        <ul className="flex flex-col gap-2.5">
          {TRUST.map((item) => (
            <li
              key={item.text}
              className="flex items-center gap-2.5 text-sm text-body"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                aria-hidden="true"
                className="shrink-0 text-accent-soft-ink"
                {...ICON}
              >
                <path d={item.path} />
              </svg>
              {item.text}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}
