import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Link } from '@tanstack/react-router'
import { Wordmark } from '#/components/Migo'

const LINK =
  'inline-flex min-h-11 items-center rounded-md px-3 text-sm font-bold text-accent-strong hover:underline lg:px-1'

export function Nav() {
  // The server HTML shows every link. Once hydrated, phones collapse them behind Menu.
  const [ready, setReady] = useState(false)
  const [open, setOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), 0)
    return () => window.clearTimeout(timer)
  }, [])

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape' && open) {
      setOpen(false)
      buttonRef.current?.focus()
    }
  }

  return (
    <header
      onKeyDown={onKeyDown}
      className="z-40 flex flex-wrap items-center gap-x-2 gap-y-2 py-3 lg:gap-x-6 lg:sticky lg:top-3 lg:my-3 lg:rounded-full lg:border lg:border-border lg:bg-surface/90 lg:px-6 lg:py-2 lg:shadow-sm lg:backdrop-blur"
    >
      <a
        href="#top"
        aria-label="Jobmigo home"
        className="mr-auto inline-flex min-h-11 items-center"
      >
        <Wordmark />
      </a>
      <nav
        id="site-nav"
        aria-label="Site"
        onClick={(event) => {
          if ((event.target as HTMLElement).closest('a')) setOpen(false)
        }}
        className={`order-last flex basis-full flex-col rounded-xl border border-border bg-surface p-2 shadow-sm lg:order-none lg:basis-auto lg:flex-row lg:items-center lg:gap-x-5 lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none ${
          ready && !open ? 'max-lg:hidden' : ''
        }`}
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
      </nav>
      <a
        href="#waitlist"
        className="inline-flex min-h-11 items-center rounded-full bg-accent-strong px-3 text-sm font-bold text-white sm:px-4 transition-colors hover:bg-accent-strong-hover"
      >
        {/* One flex item, so the space before "the waitlist" is not trimmed. */}
        <span>
          Join<span className="max-[430px]:sr-only"> the waitlist</span>
        </span>
      </a>
      {ready && (
        <button
          ref={buttonRef}
          type="button"
          aria-expanded={open}
          aria-controls="site-nav"
          onClick={() => setOpen((value) => !value)}
          className="inline-flex min-h-11 items-center rounded-full border border-border-strong bg-surface px-3 text-sm font-bold text-ink sm:px-4 hover:bg-surface-muted lg:hidden"
        >
          {open ? 'Close' : 'Menu'}
        </button>
      )}
    </header>
  )
}
