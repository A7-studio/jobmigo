import { HeroDemo } from './HeroDemo'

export function Hero() {
  return (
    <section
      aria-labelledby="hero"
      className="flex flex-wrap items-center gap-10 pt-12 pb-16 md:pb-20"
    >
      <div className="flex min-w-0 flex-[1_1_460px] flex-col gap-6">
        <span className="inline-flex self-start rounded-full bg-accent-soft px-3.5 py-1.5 text-sm font-bold text-accent-soft-ink">
          AI job-application assistant · Early access
        </span>
        <h1
          id="hero"
          className="text-5xl leading-none font-extrabold tracking-tight md:text-7xl"
        >
          Skip the ghost pipeline.{' '}
          <span className="text-accent-strong">Apply with your best case.</span>
        </h1>
        <p className="max-w-xl text-lg leading-relaxed text-body md:text-xl">
          Jobmigo is being built as your AI job assistant. It will check whether
          jobs look really open, make your CV readable by hiring systems, and
          help you reach the people who decide. We help you apply better.
          Employers make the hiring decision.
        </p>
        <div className="flex flex-wrap gap-3">
          <a
            href="#waitlist"
            className="inline-flex min-h-12 items-center rounded-full bg-accent-strong px-6 text-base font-bold text-white transition-colors hover:bg-accent-strong-hover"
          >
            Join the waitlist
          </a>
          <a
            href="#how"
            className="inline-flex min-h-12 items-center rounded-full border border-border-strong bg-surface px-6 text-base font-bold text-ink hover:bg-surface-muted"
          >
            See how it works
          </a>
        </div>
        <p className="text-sm text-faint">
          Early access · AI proposes, you decide · Your CV will stay private
        </p>
      </div>

      <div className="relative flex min-h-[460px] min-w-[300px] flex-[1_1_380px] items-center justify-center py-8">
        <div
          aria-hidden="true"
          className="absolute top-1/2 left-1/2 aspect-square w-[min(380px,100%)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent-soft"
        />
        <HeroDemo />
      </div>
    </section>
  )
}
