import { useEffect, useRef, useState } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BTN_PRIMARY, MigoSays, Problem } from '#/components/cv/parts'
import { AddJob } from '#/components/jobs/add-job'
import { JobRow } from '#/components/jobs/job-row'
import type { RowActions } from '#/components/jobs/job-row'
import { deleteJob, listJobs, setJobStatus } from '#/lib/jobs-api'
import type { Job, JobStatus } from '#/lib/jobs-api'
import type { Result } from '#/lib/profile-api'
import { jobsCopy } from '#/lib/jobs-view'

export const Route = createFileRoute('/_app/jobs')({
  head: () => ({ meta: [{ title: 'Jobs | Jobmigo' }] }),
  component: JobsPage,
})

class LoadError extends Error {
  readonly code: string
  constructor(code: string) {
    super(code)
    this.code = code
  }
}

const VIEWS: { value: JobStatus; label: string }[] = [
  { value: 'saved', label: 'Saved' },
  { value: 'dismissed', label: 'Dismissed' },
]

function JobsPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [view, setView] = useState<JobStatus>('saved')
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const announced = useRef(0)
  const heading = useRef<HTMLHeadingElement>(null)
  const addButton = useRef<HTMLButtonElement>(null)
  // A repeated message is changed invisibly so a screen reader says it again.
  const announce = (message: string) => {
    announced.current += 1
    setNotice(message + (announced.current % 2 === 0 ? '​' : ''))
  }

  const query = useQuery({
    queryKey: ['jobs', view],
    queryFn: async (): Promise<Job[]> => {
      const result = await listJobs(view)
      if (!result.ok) throw new LoadError(result.code)
      return result.data
    },
    retry: false,
  })
  const loadCode = query.error instanceof LoadError ? query.error.code : null
  const unauthorized = loadCode === 'unauthorized'
  useEffect(() => {
    if (unauthorized) void navigate({ to: '/sign-in' })
  }, [unauthorized, navigate])
  // After a failed read show the error and no rows: stale rows must not be acted on.
  const jobs = query.isError ? undefined : query.data

  async function change<T>(
    action: () => Promise<Result<T>>,
    done: string,
  ): Promise<string | null> {
    setBusy(true)
    try {
      const result = await action()
      if (result.ok) {
        announce(done)
        await queryClient.invalidateQueries({ queryKey: ['jobs'] })
        requestAnimationFrame(() => heading.current?.focus())
        return null
      }
      if (result.code === 'unauthorized') {
        void navigate({ to: '/sign-in' })
        return ''
      }
      if (result.code === 'not_found') {
        await queryClient.invalidateQueries({ queryKey: ['jobs'] })
      }
      return jobsCopy(result.code).body
    } finally {
      setBusy(false)
    }
  }

  const actions: RowActions = {
    busy,
    setStatus: (job, status) =>
      change(
        () => setJobStatus(job.id, status),
        status === 'dismissed' ? 'Dismissed.' : 'Restored.',
      ),
    remove: (job) => change(() => deleteJob(job.id), 'Deleted.'),
  }

  return (
    <div className="mx-auto flex w-full max-w-[880px] flex-col gap-6">
      <div role="status" aria-live="polite" className="sr-only">
        {notice}
      </div>

      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1
            ref={heading}
            tabIndex={-1}
            className="font-display text-[28px] font-bold tracking-tight text-ink"
          >
            Jobs
          </h1>
          <p className="mt-1.5 text-sm text-faint">
            Jobs you add by link or by pasting the posting. Nothing here is
            scored yet.
          </p>
        </div>
        {!adding && (
          <button
            ref={addButton}
            type="button"
            className={BTN_PRIMARY}
            onClick={() => setAdding(true)}
          >
            Add a job
          </button>
        )}
      </header>

      {adding && (
        <AddJob
          onUnauthorized={() => void navigate({ to: '/sign-in' })}
          onClose={() => {
            setAdding(false)
            requestAnimationFrame(() => addButton.current?.focus())
          }}
          onSaved={async (job) => {
            setAdding(false)
            setView('saved')
            announce(`Saved ${job.title} at ${job.company}.`)
            await queryClient.invalidateQueries({ queryKey: ['jobs'] })
            requestAnimationFrame(() => heading.current?.focus())
          }}
        />
      )}

      <div
        role="group"
        aria-label="Which jobs"
        className="flex flex-wrap gap-2.5"
      >
        {VIEWS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={view === option.value}
            disabled={busy}
            onClick={() => setView(option.value)}
            className={`inline-flex min-h-10 items-center rounded-full border px-4 text-[13px] font-semibold ${
              view === option.value
                ? 'border-ink bg-ink text-white'
                : 'border-border-strong bg-surface text-muted hover:bg-surface-muted'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {query.isPending && (
        <div
          role="status"
          aria-label="Loading your jobs"
          className="flex animate-pulse flex-col gap-3"
        >
          <div className="h-20 rounded-2xl bg-surface-sunken" />
          <div className="h-20 rounded-2xl bg-surface-sunken" />
        </div>
      )}

      {loadCode && !unauthorized && (
        <Problem
          title="We could not load your jobs"
          body="Your jobs are safe. Try again in a moment."
        >
          <button
            type="button"
            className={BTN_PRIMARY}
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            {query.isFetching ? 'Trying…' : 'Try again'}
          </button>
        </Problem>
      )}

      {jobs && jobs.length === 0 && (
        <section className="flex max-w-xl flex-col gap-3.5 rounded-[20px] border border-border bg-surface p-6">
          {view === 'saved' ? (
            <>
              <MigoSays>Nothing saved yet.</MigoSays>
              <h2 className="font-display text-[17px] font-bold text-ink">
                No jobs yet
              </h2>
              <p className="text-[13px] leading-relaxed text-muted">
                Add a job by pasting its link, or by pasting the posting text.
                We keep a cleaned copy so you can read it later.
              </p>
              {!adding && (
                <button
                  type="button"
                  className={`${BTN_PRIMARY} self-start`}
                  onClick={() => setAdding(true)}
                >
                  Add a job
                </button>
              )}
            </>
          ) : (
            <p className="text-sm text-faint">
              No dismissed jobs. A job you dismiss waits here until you restore
              or delete it.
            </p>
          )}
        </section>
      )}

      {jobs && jobs.length > 0 && (
        <section
          aria-label={view === 'saved' ? 'Saved jobs' : 'Dismissed jobs'}
          className="rounded-[20px] border border-border bg-surface p-2"
        >
          <ul className="m-0 list-none p-0">
            {jobs.map((job) => (
              <JobRow key={job.id} job={job} actions={actions} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
