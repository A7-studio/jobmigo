import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { Migo } from '#/components/Migo'
import { Pill } from './Feature'

const MET = 6
const TOTAL = 7

const CHECKS = [
  { text: 'Posting is live', note: 'Posted 2 days ago', label: 'Live' },
  { text: 'Salary range listed', note: 'Before you apply', label: 'Listed' },
  { text: 'Not a repost', note: 'First time seen', label: 'Clear' },
]

const CLAIMS = [
  { text: 'Led a team of four', tone: 'good', label: 'Verified' },
  { text: 'Offline-first sync', tone: 'info', label: 'Reworded' },
  { text: 'Regulated-industry controls', tone: 'warn', label: 'Confirm it' },
] as const

/** Staggers one block of the sequence. Reduced motion turns the animation off globally. */
function at(seconds: number): CSSProperties {
  return { animationDelay: `${seconds}s` }
}

function Run({ onReplay }: { onReplay: () => void }) {
  // The server renders the final value; motion-friendly visitors see it count up.
  const [met, setMet] = useState(MET)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let interval: number | undefined
    const reset = window.setTimeout(() => setMet(0), 0)
    const start = window.setTimeout(() => {
      interval = window.setInterval(() => {
        setMet((value) => {
          if (value >= MET) {
            window.clearInterval(interval)
            return value
          }
          return value + 1
        })
      }, 140)
    }, 1700)
    return () => {
      window.clearTimeout(reset)
      window.clearTimeout(start)
      window.clearInterval(interval)
    }
  }, [])

  return (
    <div
      role="group"
      aria-label="Preview of an evaluation for a sample job"
      className="relative z-10 w-full max-w-[400px] rounded-xl border border-border bg-surface p-4 shadow-md"
    >
      <div
        className="nod absolute -top-9 -right-3"
        style={{ '--nod-delay': '2.6s' } as CSSProperties}
      >
        <Migo size={64} />
      </div>

      <div className="flex items-center justify-between gap-2">
        <span className="rounded-full bg-neutral-bg px-2.5 py-1 text-xs font-bold text-neutral-ink">
          Preview · sample job
        </span>
        <button
          type="button"
          onClick={onReplay}
          aria-label="Replay the sample evaluation"
          className="inline-flex min-h-11 items-center rounded-full px-3 text-xs font-bold text-accent-strong hover:bg-accent-wash"
        >
          Replay
        </button>
      </div>

      <div className="rise flex items-center gap-3 py-2" style={at(0.2)}>
        <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent-soft font-extrabold text-accent-soft-ink">
          L
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-bold text-ink">
            Senior Flutter Engineer
          </span>
          <span className="block text-xs text-muted">
            Lumen Health · Remote
          </span>
        </span>
      </div>

      <ul className="flex flex-col divide-y divide-border border-t border-border">
        {CHECKS.map((check, index) => (
          <li
            key={check.text}
            className="rise flex items-center justify-between gap-3 py-2"
            style={at(0.6 + index * 0.3)}
          >
            <span className="min-w-0">
              <span className="block text-sm font-bold text-ink">
                {check.text}
              </span>
              <span className="block text-xs text-muted">{check.note}</span>
            </span>
            <Pill tone="good">{check.label}</Pill>
          </li>
        ))}
      </ul>

      <div
        className="rise flex flex-wrap items-center justify-between gap-2 border-t border-border py-2.5"
        style={at(1.6)}
      >
        <span className="text-sm font-bold text-ink">
          <span aria-hidden="true">
            {met} of {TOTAL}
          </span>
          <span className="sr-only">
            {MET} of {TOTAL}
          </span>{' '}
          must-haves evidenced
        </span>
        <span className="pop" style={at(2.6)}>
          <Pill tone="good">Strong fit</Pill>
        </span>
      </div>

      <div
        className="rise flex items-start gap-3 rounded-lg bg-surface-muted p-2.5"
        style={at(2.9)}
      >
        <Pill tone="bad">✕ Gap</Pill>
        <span className="min-w-0">
          <span className="block text-sm font-bold text-ink">
            Native iOS (Swift)
          </span>
          <span className="block text-xs text-muted">
            Nothing in your profile yet
          </span>
        </span>
      </div>

      <ul className="mt-2 flex flex-col divide-y divide-border border-t border-border">
        {CLAIMS.map((claim, index) => (
          <li
            key={claim.text}
            className="rise flex items-center justify-between gap-3 py-2"
            style={at(3.3 + index * 0.3)}
          >
            <span className="text-sm font-bold text-ink">{claim.text}</span>
            <Pill tone={claim.tone}>{claim.label}</Pill>
          </li>
        ))}
      </ul>

      <p className="pt-1 text-xs text-faint">
        Sample only. Jobmigo is in early access.
      </p>
    </div>
  )
}

export function HeroDemo() {
  const [run, setRun] = useState(0)
  return <Run key={run} onReplay={() => setRun((value) => value + 1)} />
}
