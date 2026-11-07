import { Link } from '@tanstack/react-router'
import { Wordmark } from '#/components/Migo'

const LINK =
  'inline-flex min-h-11 items-center rounded-md px-1 text-sm font-bold text-accent-strong hover:underline'

export function Nav() {
  return (
    <header className="z-40 flex flex-wrap items-center justify-between gap-x-7 gap-y-3 py-5 lg:sticky lg:top-3 lg:my-3 lg:rounded-full lg:border lg:border-border lg:bg-surface/90 lg:px-6 lg:py-2 lg:shadow-sm lg:backdrop-blur">
      <a
        href="#top"
        aria-label="Jobmigo home"
        className="inline-flex min-h-11 items-center"
      >
        <Wordmark />
      </a>
      <nav
        aria-label="Site"
        className="flex flex-wrap items-center gap-x-6 gap-y-1"
      >
        <a className={LINK} href="#how">
          How it works
        </a>
        <a className={LINK} href="#features">
          Features
        </a>
        <a className={LINK} href="#honest">
          Honest by design
        </a>
        <Link className={LINK} to="/sign-in">
          Sign in
        </Link>
        <a
          href="#waitlist"
          className="inline-flex min-h-11 items-center rounded-full bg-accent-strong px-4 text-sm font-bold text-white transition-colors hover:bg-accent-strong-hover"
        >
          Join the waitlist
        </a>
      </nav>
    </header>
  )
}
