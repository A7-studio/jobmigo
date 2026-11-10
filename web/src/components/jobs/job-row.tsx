import { useEffect, useRef, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { BTN, BTN_GHOST, BTN_PRIMARY, Problem } from '#/components/cv/parts'
import { getJob } from '#/lib/jobs-api'
import type { Job } from '#/lib/jobs-api'
import {
  addedLabel,
  initialOf,
  jobsCopy,
  safeHref,
  sourceHost,
} from '#/lib/jobs-view'

const TINTS = [
  'bg-accent-soft text-accent-soft-ink',
  'bg-good-bg text-good-ink',
  'bg-neutral-bg text-neutral-ink',
]

/** A stable tile colour from the company name. */
const tint = (company: string) => {
  let sum = 0
  for (const ch of company) sum += ch.codePointAt(0) ?? 0
  return TINTS[sum % TINTS.length]
}

export type RowActions = {
  busy: boolean
  /** Runs one change; returns an error sentence, or null when it worked. */
  setStatus: (job: Job, status: 'saved' | 'dismissed') => Promise<string | null>
  remove: (job: Job) => Promise<string | null>
}

/** One job: what we stored, and what you can do with it. */
export function JobRow({ job, actions }: { job: Job; actions: RowActions }) {
  const [asking, setAsking] = useState(false)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const keep = useRef<HTMLButtonElement>(null)
  const deleteButton = useRef<HTMLButtonElement>(null)
  const asked = useRef(false)
  const host = sourceHost(job.sourceUrl)
  const href = safeHref(job.sourceUrl)
  const dismissed = job.status === 'dismissed'

  // The safe choice gets focus when the question appears; the button returns it on Keep.
  useEffect(() => {
    if (asking) {
      asked.current = true
      keep.current?.focus()
    } else if (asked.current) {
      asked.current = false
      deleteButton.current?.focus()
    }
  }, [asking])

  const text = useQuery({
    queryKey: ['job', job.id],
    queryFn: async () => {
      const result = await getJob(job.id)
      if (!result.ok) throw new Error(result.code)
      return result.data.description
    },
    enabled: open,
    retry: false,
    staleTime: Infinity,
  })

  const meta = [host, addedLabel(job.createdAt)].filter(Boolean).join(' · ')

  return (
    <li className="flex flex-col gap-3 border-t border-surface-sunken px-4 py-4 first:border-t-0">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div
          aria-hidden="true"
          className={`flex size-11 shrink-0 items-center justify-center rounded-xl text-[17px] font-extrabold ${tint(job.company)}`}
        >
          {initialOf(job.company)}
        </div>
        <div className="min-w-0 flex-[1_1_260px]">
          <p className="break-words text-[15px] font-bold text-ink">
            {job.title}
          </p>
          <p className="mt-0.5 break-words text-[13px] text-muted">
            {job.company}
            {job.location ? ` · ${job.location}` : ''}
          </p>
          <p className="mt-1 break-words text-xs text-faint">{meta}</p>
        </div>
        {job.flag === 'review' && (
          <span className="rounded-full bg-warn-bg px-3 py-1.5 text-xs font-extrabold text-warn-ink">
            Check this posting
          </span>
        )}
        <div className="flex flex-wrap items-center gap-1.5">
          {asking ? (
            <div
              role="group"
              aria-label={`Delete ${job.title}?`}
              className="flex flex-wrap items-center gap-2"
            >
              <span className="text-[13px] font-bold text-bad-ink">
                Delete this job for good?
              </span>
              <button
                type="button"
                className={BTN_PRIMARY}
                disabled={actions.busy}
                onClick={async () => {
                  const failure = await actions.remove(job)
                  if (failure) setError(failure)
                }}
              >
                Delete
              </button>
              <button
                ref={keep}
                type="button"
                className={BTN}
                disabled={actions.busy}
                onClick={() => setAsking(false)}
              >
                Keep
              </button>
            </div>
          ) : (
            <>
              <button
                type="button"
                className={BTN_GHOST}
                disabled={actions.busy}
                aria-label={`${dismissed ? 'Restore' : 'Dismiss'} ${job.title} at ${job.company}`}
                onClick={async () => {
                  setError(null)
                  const failure = await actions.setStatus(
                    job,
                    dismissed ? 'saved' : 'dismissed',
                  )
                  if (failure) setError(failure)
                }}
              >
                {dismissed ? 'Restore' : 'Dismiss'}
              </button>
              <button
                ref={deleteButton}
                type="button"
                className={BTN_GHOST}
                disabled={actions.busy}
                aria-label={`Delete ${job.title} at ${job.company}`}
                onClick={() => {
                  setError(null)
                  setAsking(true)
                }}
              >
                Delete
              </button>
            </>
          )}
        </div>
      </div>

      {job.flag === 'review' && (
        <p className="text-[13px] leading-relaxed text-body">
          Parts of this text looked like instructions or were hidden, so we kept
          only what a reader sees. Read it before you rely on it.
        </p>
      )}

      {error && (
        <p role="alert" className="text-sm font-bold text-bad-ink">
          {error}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`text-${job.id}`}
          className="inline-flex min-h-11 items-center text-[13px] font-bold text-accent-soft-ink underline-offset-2 hover:underline"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? 'Hide the text we saved' : 'Read the text we saved'}
        </button>
        <Link
          to="/jobs/$jobId"
          params={{ jobId: job.id }}
          aria-label={`Open ${job.title} at ${job.company}`}
          className="inline-flex min-h-11 items-center text-[13px] font-bold text-accent-soft-ink underline-offset-2 hover:underline"
        >
          Open
        </Link>
        {href && (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center text-[13px] font-bold text-accent-soft-ink underline-offset-2 hover:underline"
          >
            Open the original posting
          </a>
        )}
      </div>
      {open && (
        <div id={`text-${job.id}`}>
          {text.isPending && (
            <p role="status" className="text-sm text-faint">
              Loading the text…
            </p>
          )}
          {text.isError && (
            <Problem
              title={jobsCopy(text.error.message).title}
              body={jobsCopy(text.error.message).body}
            />
          )}
          {text.data !== undefined && (
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-2xl border border-border bg-bg p-4 font-sans text-sm leading-relaxed text-body">
              {text.data}
            </pre>
          )}
        </div>
      )}
    </li>
  )
}
