import type { ReactNode } from 'react'

export function PreviewCard({
  title,
  children,
  note,
}: {
  title: string
  children: ReactNode
  note?: string
}) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-bold text-ink">{title}</p>
        <span className="rounded-full bg-neutral-bg px-2.5 py-1 text-xs font-bold text-neutral-ink">
          Preview
        </span>
      </div>
      {children}
      {note && <p className="text-sm text-muted">{note}</p>}
    </div>
  )
}

export function Pill({
  tone,
  children,
}: {
  tone: 'good' | 'info' | 'warn' | 'bad' | 'neutral'
  children: ReactNode
}) {
  const classes = {
    good: 'bg-good-bg text-good-ink',
    info: 'bg-info-bg text-info-ink',
    warn: 'bg-warn-bg text-warn-ink',
    bad: 'bg-bad-bg text-bad-ink',
    neutral: 'bg-neutral-bg text-neutral-ink',
  }[tone]
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-extrabold whitespace-nowrap ${classes}`}
    >
      {children}
    </span>
  )
}

export function FeatureSection({
  id,
  eyebrow,
  title,
  body,
  points,
  children,
  flip = false,
}: {
  id?: string
  eyebrow: string
  title: string
  body: string
  points: string[]
  children: ReactNode
  flip?: boolean
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${eyebrow}-h`}
      className={`flex flex-wrap items-center gap-10 pb-20 md:pb-24 ${flip ? 'flex-row-reverse' : ''}`}
    >
      <div className="flex min-w-0 flex-[1_1_380px] flex-col gap-4">
        <span className="text-sm font-bold text-accent-strong">{eyebrow}</span>
        <h2
          id={`${eyebrow}-h`}
          className="text-3xl leading-tight font-bold md:text-4xl"
        >
          {title}
        </h2>
        <p className="text-base leading-relaxed text-body md:text-lg">{body}</p>
        <ul className="flex flex-col gap-2 text-base text-body">
          {points.map((point) => (
            <li key={point} className="flex gap-2">
              <span aria-hidden="true" className="font-bold text-accent-strong">
                ✓
              </span>
              {point}
            </li>
          ))}
        </ul>
      </div>
      <div className="min-w-0 flex-[1_1_360px]">{children}</div>
    </section>
  )
}
