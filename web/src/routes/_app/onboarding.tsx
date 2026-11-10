import { useEffect, useRef, useState } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BTN,
  BTN_GHOST,
  BTN_PRIMARY,
  Dropzone,
  FileCard,
  MigoSays,
  Problem,
  StepList,
  Stepper,
  TrustBox,
  Working,
} from '#/components/cv/parts'
import { deleteCv, getDraft, listCvs, startParse, uploadCv } from '#/lib/cv-api'
import type { Draft } from '#/lib/cv-api'
import {
  POLL_INTERVAL_MS,
  POLL_LIMIT_MS,
  copyFor,
  screenFor,
  shouldKeepPolling,
  summarise,
  validateFile,
} from '#/lib/cv-view'
import type { Copy, CvRow } from '#/lib/cv-view'

export const Route = createFileRoute('/_app/onboarding')({
  head: () => ({ meta: [{ title: 'Upload your CV | Jobmigo' }] }),
  component: Onboarding,
})

const SLOW_AFTER_MS = 90_000

class CvError extends Error {
  readonly code: string
  constructor(code: string) {
    super(code)
    this.code = code
  }
}

const kb = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`

function Onboarding() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const startedRef = useRef<number | null>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [busy, setBusy] = useState<'upload' | 'parse' | 'delete' | null>(null)
  const [problem, setProblem] = useState<Copy | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const list = useQuery({
    queryKey: ['cvs'],
    queryFn: async () => {
      const result = await listCvs()
      if (!result.ok) throw new CvError(result.code)
      return result.data.items
    },
    refetchInterval: (query) => {
      const latest = query.state.data?.[0]
      if (latest?.parseStatus !== 'parsing') return false
      const started = startedRef.current
      if (started === null) return POLL_INTERVAL_MS
      return shouldKeepPolling('parsing', started, Date.now())
        ? POLL_INTERVAL_MS
        : false
    },
  })

  const latest: CvRow | null = list.data?.[0] ?? null
  const screen = screenFor(latest)
  const loadFailed = list.error instanceof CvError ? list.error.code : null

  const draft = useQuery({
    queryKey: ['cvs', 'draft', latest?.id],
    queryFn: async (): Promise<Draft> => {
      const result = await getDraft(latest?.id ?? '')
      if (!result.ok) throw new CvError(result.code)
      return result.data
    },
    enabled: screen.kind === 'parsed' && latest !== null,
  })

  // Time spent parsing drives the "taking longer" and "check again" notes.
  useEffect(() => {
    if (screen.kind !== 'parsing') {
      startedRef.current = null
      setElapsedMs(0)
      return
    }
    startedRef.current ??= Date.now()
    const timer = setInterval(
      () => setElapsedMs(Date.now() - (startedRef.current ?? Date.now())),
      5_000,
    )
    return () => clearInterval(timer)
  }, [screen.kind])

  // A session that ended mid-visit goes back to sign-in.
  const unauthorized = loadFailed === 'unauthorized'
  useEffect(() => {
    if (unauthorized) void navigate({ to: '/sign-in' })
  }, [unauthorized, navigate])

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['cvs'] })

  // A problem is shown calmly; an ended session goes back to sign-in instead.
  function fail(code: string) {
    if (code === 'unauthorized') void navigate({ to: '/sign-in' })
    else setProblem(copyFor(code))
  }

  // After the screen changes under the user, put focus on the heading.
  const settleFocus = () =>
    requestAnimationFrame(() => headingRef.current?.focus())

  async function chooseFile(file: File) {
    setProblem(null)
    setConfirmDelete(false)
    const check = validateFile(file)
    if (!check.ok) {
      fail(check.code)
      return
    }
    setBusy('upload')
    try {
      // One CV at a time: a failed one is replaced by the new file.
      if (latest) {
        const removed = await deleteCv(latest.id)
        if (!removed.ok && removed.code !== 'not_found') {
          fail(removed.code)
          return
        }
      }
      const uploaded = await uploadCv(file)
      if (!uploaded.ok) fail(uploaded.code)
      await refresh()
      settleFocus()
    } finally {
      setBusy(null)
    }
  }

  async function build() {
    if (!latest) return
    setProblem(null)
    setBusy('parse')
    try {
      const started = await startParse(latest.id)
      if (!started.ok) fail(started.code)
      startedRef.current = Date.now()
      await refresh()
    } finally {
      setBusy(null)
    }
  }

  async function remove() {
    if (!latest) return
    setProblem(null)
    setBusy('delete')
    try {
      const removed = await deleteCv(latest.id)
      if (!removed.ok && removed.code !== 'not_found') fail(removed.code)
      setConfirmDelete(false)
      await refresh()
      settleFocus()
    } finally {
      setBusy(null)
    }
  }

  const working = busy !== null

  return (
    <div className="mx-auto flex max-w-[1080px] flex-col items-center gap-7">
      <Stepper />
      <section
        aria-labelledby="up"
        className="rise flex w-full max-w-[640px] flex-col gap-5 rounded-[20px] border border-border bg-surface p-5 sm:p-7"
      >
        <MigoSays>
          Hi, I’m Migo. Drop in your CV and I’ll do the boring bit.
        </MigoSays>
        <div>
          <h1
            id="up"
            ref={headingRef}
            tabIndex={-1}
            className="font-display text-[26px] font-bold tracking-tight text-ink"
          >
            Start with your CV
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            An AI model reads it once to build a draft of your profile. It’s
            only a draft: nothing is scored or written from it yet.
          </p>
        </div>

        {problem && screen.kind !== 'failed' && (
          <Problem title={problem.title} body={problem.body} />
        )}

        {list.isPending && (
          <div
            role="status"
            aria-label="Loading your CV"
            className="flex animate-pulse flex-col gap-3"
          >
            <div className="h-24 rounded-2xl bg-surface-sunken" />
          </div>
        )}

        {loadFailed && !unauthorized && (
          <Problem
            title={copyFor(loadFailed).title}
            body={copyFor(loadFailed).body}
          >
            <button
              type="button"
              className={BTN_PRIMARY}
              disabled={list.isFetching}
              onClick={() => void list.refetch()}
            >
              {list.isFetching ? 'Trying…' : 'Try again'}
            </button>
          </Problem>
        )}

        {!list.isPending && !loadFailed && screen.kind === 'empty' && (
          <Dropzone
            onFile={(file) => void chooseFile(file)}
            disabled={working}
            busy={busy === 'upload'}
          />
        )}

        {screen.kind === 'ready' && (
          <>
            <FileCard
              name={screen.cv.filename}
              status={`Uploaded, ${kb(screen.cv.sizeBytes)}`}
            >
              <StepList
                items={[
                  { text: 'File stored privately', state: 'done' },
                  { text: 'Text extracted', state: 'done' },
                ]}
              />
            </FileCard>
            <div className="flex flex-wrap gap-2.5">
              <button
                type="button"
                className={BTN_PRIMARY}
                disabled={working}
                onClick={() => void build()}
              >
                {busy === 'parse' ? 'Starting…' : 'Build my profile draft'}
              </button>
              <DeleteControl
                confirm={confirmDelete}
                busy={busy === 'delete'}
                disabled={working}
                onAsk={() => setConfirmDelete(true)}
                onCancel={() => setConfirmDelete(false)}
                onConfirm={() => void remove()}
              />
            </div>
          </>
        )}

        {screen.kind === 'parsing' && (
          <div role="status" className="flex flex-col gap-3">
            <FileCard name={screen.cv.filename} status="Reading your CV">
              <Working label="Reading your CV" />
              <StepList
                items={[
                  { text: 'File stored privately', state: 'done' },
                  { text: 'Text extracted', state: 'done' },
                  {
                    text: 'Finding experience, skills and achievements',
                    state: 'working',
                  },
                ]}
              />
            </FileCard>
            {elapsedMs >= POLL_LIMIT_MS ? (
              <div className="flex flex-wrap items-center gap-2.5 text-[13px] text-muted">
                This is taking much longer than usual.
                <button
                  type="button"
                  className={BTN}
                  onClick={() => {
                    startedRef.current = Date.now()
                    setElapsedMs(0)
                    void list.refetch()
                  }}
                >
                  Check again
                </button>
              </div>
            ) : elapsedMs >= SLOW_AFTER_MS ? (
              <p className="text-[13px] text-muted">
                This is taking longer than usual. You can leave this page; the
                reading keeps going.
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2.5">
              <DeleteControl
                confirm={confirmDelete}
                busy={busy === 'delete'}
                disabled={working}
                onAsk={() => setConfirmDelete(true)}
                onCancel={() => setConfirmDelete(false)}
                onConfirm={() => void remove()}
              />
            </div>
          </div>
        )}

        {screen.kind === 'failed' && (
          <Problem
            title={(problem ?? screen.copy).title}
            body={(problem ?? screen.copy).body}
          >
            {screen.copy.retry && (
              <button
                type="button"
                className={BTN_PRIMARY}
                disabled={working}
                onClick={() => void build()}
              >
                {busy === 'parse' ? 'Starting…' : 'Try again'}
              </button>
            )}
            {screen.copy.another && (
              <ReplaceFile
                primary={!screen.copy.retry}
                disabled={working}
                busy={busy === 'upload'}
                onFile={(file) => void chooseFile(file)}
              />
            )}
          </Problem>
        )}

        {screen.kind === 'parsed' && (
          <ParsedView
            cv={screen.cv}
            draft={draft.data}
            loading={draft.isPending}
            failed={draft.isError}
            onRetry={() => void draft.refetch()}
            deleteControl={
              <DeleteControl
                confirm={confirmDelete}
                busy={busy === 'delete'}
                disabled={working}
                onAsk={() => setConfirmDelete(true)}
                onCancel={() => setConfirmDelete(false)}
                onConfirm={() => void remove()}
              />
            }
          />
        )}

        <TrustBox />
      </section>
    </div>
  )
}

function ReplaceFile({
  onFile,
  primary,
  disabled,
  busy,
}: {
  onFile: (file: File) => void
  primary: boolean
  disabled: boolean
  busy: boolean
}) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <>
      <input
        ref={input}
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose another CV file"
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) onFile(file)
        }}
      />
      <button
        type="button"
        className={primary ? BTN_PRIMARY : BTN}
        disabled={disabled}
        onClick={() => input.current?.click()}
      >
        {busy ? 'Uploading…' : 'Upload another file'}
      </button>
    </>
  )
}

function DeleteControl({
  confirm,
  busy,
  disabled,
  onAsk,
  onCancel,
  onConfirm,
}: {
  confirm: boolean
  busy: boolean
  disabled: boolean
  onAsk: () => void
  onCancel: () => void
  onConfirm: () => void
}) {
  const ask = useRef<HTMLButtonElement>(null)
  const keep = useRef<HTMLButtonElement>(null)
  const seenConfirm = useRef(false)

  // Move focus with the swap: to the safe choice when asking, back when cancelled.
  useEffect(() => {
    if (confirm) {
      seenConfirm.current = true
      keep.current?.focus()
    } else if (seenConfirm.current) {
      seenConfirm.current = false
      ask.current?.focus()
    }
  }, [confirm])

  if (!confirm) {
    return (
      <button
        ref={ask}
        type="button"
        className={BTN_GHOST}
        disabled={disabled}
        onClick={onAsk}
      >
        Delete this CV
      </button>
    )
  }
  return (
    <div
      role="group"
      aria-label="Confirm delete"
      className="flex flex-wrap items-center gap-2.5 text-[13px] text-muted"
    >
      <span>Delete this CV and its profile draft? This cannot be undone.</span>
      <button
        type="button"
        className="inline-flex min-h-11 items-center rounded-full bg-bad-bg px-4 text-sm font-bold text-bad-ink hover:brightness-95 disabled:opacity-60"
        disabled={disabled}
        onClick={onConfirm}
      >
        {busy ? 'Deleting…' : 'Delete'}
      </button>
      <button
        ref={keep}
        type="button"
        className={BTN}
        disabled={disabled}
        onClick={onCancel}
      >
        Keep it
      </button>
    </div>
  )
}

function ParsedView({
  cv,
  draft,
  loading,
  failed,
  onRetry,
  deleteControl,
}: {
  cv: CvRow
  draft: Draft | undefined
  loading: boolean
  failed: boolean
  onRetry: () => void
  deleteControl: React.ReactNode
}) {
  return (
    <div role="status" className="flex flex-col gap-4">
      <FileCard name={cv.filename} status="Draft ready">
        <StepList
          items={[
            { text: 'File stored privately', state: 'done' },
            { text: 'Text extracted', state: 'done' },
            { text: 'Profile draft built', state: 'done' },
          ]}
        />
      </FileCard>

      {loading && (
        <div
          aria-label="Loading your draft"
          className="h-20 animate-pulse rounded-2xl bg-surface-sunken"
        />
      )}
      {failed && (
        <Problem
          title="We could not load your draft"
          body="Your CV is safe. Try again in a moment."
        >
          <button type="button" className={BTN_PRIMARY} onClick={onRetry}>
            Try again
          </button>
        </Problem>
      )}
      {draft && (
        <div className="flex flex-col gap-3 rounded-2xl border border-border bg-bg p-4">
          <h2 className="font-display text-[17px] font-bold text-ink">
            Here’s what we found
          </h2>
          {draft.headline && (
            <p className="text-sm font-semibold text-ink">{draft.headline}</p>
          )}
          <p className="text-[13px] text-muted">
            {summarise(draft).join(', ') || 'Nothing we could list.'}
          </p>
          {draft.experiences.length > 0 && (
            <ul className="m-0 flex list-none flex-col gap-1 p-0 text-[13px] text-body">
              {draft.experiences.slice(0, 5).map((job) => (
                <li key={job.id}>
                  {job.role} at {job.company}
                  {job.start || job.end || job.isCurrent
                    ? ` (${job.start ?? '?'} to ${job.isCurrent ? 'now' : (job.end ?? '?')})`
                    : ''}
                </li>
              ))}
            </ul>
          )}
          <p className="text-[13px] leading-relaxed text-muted">
            These are unconfirmed: the AI can get things wrong. Reviewing and
            correcting them is the next step, and it isn’t built yet.
          </p>
        </div>
      )}
      <div className="flex flex-wrap gap-2.5">{deleteControl}</div>
    </div>
  )
}
