import { useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Migo } from '#/components/Migo'

const ICON = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

export const BTN =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-border-strong bg-surface px-5 text-sm font-bold text-ink transition hover:-translate-y-px hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0'
export const BTN_PRIMARY =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-accent-strong bg-accent-strong px-5 text-sm font-bold text-white transition hover:-translate-y-px hover:bg-accent-strong-hover disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0'
export const BTN_GHOST =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-3.5 text-sm font-bold text-accent-soft-ink transition hover:bg-accent-wash'

const STEPS = [
  'Upload CV',
  'Review profile',
  'Make it yours',
  'First evaluation',
]

/** The four-step progress pills from the Onboarding board. Only step 1 exists yet. */
export function Stepper() {
  return (
    <ol
      aria-label="Setup progress"
      className="flex w-full max-w-[880px] list-none flex-wrap justify-center gap-2.5 p-0"
    >
      {STEPS.map((label, index) => (
        <li
          key={label}
          aria-current={index === 0 ? 'step' : undefined}
          className={`flex items-center gap-2.5 rounded-full px-3.5 py-2 text-[13px] font-bold ${
            index === 0 ? 'bg-accent-strong text-white' : 'bg-border text-muted'
          }`}
        >
          <span className="font-extrabold">{index + 1}</span>
          {label}
        </li>
      ))}
    </ol>
  )
}

export function MigoSays({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-end gap-3.5">
      <Migo size={72} label="Migo, the Jobmigo mascot" />
      <p className="rounded-[16px_16px_16px_4px] border border-accent-light bg-accent-wash px-4 py-3 text-sm leading-relaxed text-body">
        {children}
      </p>
    </div>
  )
}

/** The calm card used for every problem: says what happened and what to do next. */
export function Problem({
  title,
  body,
  children,
}: {
  title: string
  body: string
  children?: ReactNode
}) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-2xl border border-[#e8a9a9] bg-surface p-4"
    >
      <h2 className="font-display text-[17px] font-bold text-ink">{title}</h2>
      <p className="text-[13px] leading-relaxed text-muted">{body}</p>
      {children && (
        <div className="flex flex-wrap gap-2.5 pt-1">{children}</div>
      )}
    </div>
  )
}

export function Dropzone({
  onFile,
  disabled,
  busy,
}: {
  onFile: (file: File) => void
  disabled: boolean
  busy: boolean
}) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault()
        setOver(false)
        const file = event.dataTransfer.files.item(0)
        if (file && !disabled) onFile(file)
      }}
      className={`flex flex-col items-center gap-2.5 rounded-[20px] border-2 border-dashed px-5 py-8 text-center ${
        over
          ? 'border-accent bg-accent-wash'
          : 'border-accent-light bg-surface-muted'
      }`}
    >
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="text-accent-strong"
        {...ICON}
      >
        <path d="M12 16V4M7 9l5-5 5 5M4 20h16" />
      </svg>
      <div aria-live="polite" className="text-[15px] font-bold text-ink">
        {busy ? 'Uploading your CV…' : 'Drop your CV here'}
      </div>
      <div className="text-[13px] text-faint">PDF or DOCX, up to 5 MB</div>
      <input
        ref={input}
        id="cv-file"
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose your CV file"
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) onFile(file)
        }}
      />
      <button
        type="button"
        className={BTN}
        disabled={disabled}
        onClick={() => input.current?.click()}
      >
        Choose a file
      </button>
    </div>
  )
}

export function FileCard({
  name,
  status,
  children,
}: {
  name: string
  status: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border p-4">
      <div className="flex justify-between gap-3 text-sm font-bold text-ink">
        <span className="min-w-0 break-words">{name}</span>
        <span className="shrink-0 font-semibold text-faint">{status}</span>
      </div>
      {children}
    </div>
  )
}

export function StepList({
  items,
}: {
  items: { text: string; state: 'done' | 'working' }[]
}) {
  return (
    <ul className="m-0 flex list-none flex-col gap-1.5 p-0 text-[13px] text-muted">
      {items.map((item) => (
        <li key={item.text}>
          <span aria-hidden="true">{item.state === 'done' ? '✓ ' : '◐ '}</span>
          <span className="sr-only">
            {item.state === 'done' ? 'Done: ' : 'In progress: '}
          </span>
          {item.text}
        </li>
      ))}
    </ul>
  )
}

/** A bar for work whose length we cannot know: no percentage is shown. */
export function Working({ label }: { label: string }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      className="h-2 overflow-hidden rounded-full bg-surface-sunken"
    >
      <div className="indeterminate h-full w-2/5 rounded-full bg-accent" />
    </div>
  )
}

const TRUST_ICON = {
  lock: 'M6 11h12v9H6zM8 11V8a4 4 0 018 0v3',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
  check: 'M5 12l5 5 9-10',
} as const

/** What is true today about this CV, in three lines. */
export function TrustBox() {
  const rows = [
    { icon: TRUST_ICON.lock, text: 'Stored privately. Only you can see it.' },
    {
      icon: TRUST_ICON.shield,
      text: 'When you ask us to build your profile, the text of your CV (not the file) is sent to our AI provider, DeepSeek. Nothing is sent before that.',
    },
    {
      icon: TRUST_ICON.check,
      text: 'You can delete your CV from this page at any time. That also deletes the profile draft made from it.',
    },
  ]
  return (
    <div className="flex flex-col gap-2.5 rounded-2xl border border-border bg-bg p-4">
      {rows.map((row) => (
        <div
          key={row.icon}
          className="flex items-center gap-2.5 text-[13px] leading-snug text-body"
        >
          <span className="shrink-0 text-accent-soft-ink">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              aria-hidden="true"
              {...ICON}
            >
              <path d={row.icon} />
            </svg>
          </span>
          {row.text}
        </div>
      ))}
    </div>
  )
}
