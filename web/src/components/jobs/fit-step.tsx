import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BTN, BTN_PRIMARY, Problem } from '#/components/cv/parts'
import {
  checkRows,
  evaluationFor,
  fitCopy,
  importanceLabel,
  pickTrack,
  sortRequirements,
  statusLabel,
} from '#/lib/fit-view'
import { evaluateJob, getJobEvaluations } from '#/lib/jobs-api'
import type { Evaluation, RequirementStatus } from '#/lib/jobs-api'
import { bandLabel } from '#/lib/jobs-view'
import { kindLabel } from '#/lib/opportunity'
import type { OpportunityKind } from '#/lib/opportunity'
import { listTracks } from '#/lib/tracks-api'

class StepError extends Error {
  readonly code: string
  constructor(code: string) {
    super(code)
    this.code = code
  }
}

const TONE: Record<'good' | 'warn' | 'neutral', string> = {
  good: 'text-accent-soft-ink',
  warn: 'text-ink',
  neutral: 'text-muted',
}

const MARK: Record<'good' | 'warn' | 'neutral', string> = {
  good: '✓',
  warn: '!',
  neutral: '–',
}

const STATUS_MARK: Record<RequirementStatus, string> = {
  met: '✓',
  partial: '◐',
  gap: '!',
  unknown: '?',
}

/** The Fit step: the kept evaluation for one track, and the button that makes or refreshes it. */
export function FitStep({
  jobId,
  kind,
}: {
  jobId: string
  kind: OpportunityKind
}) {
  const client = useQueryClient()
  const [chosen, setChosen] = useState<string | null>(null)

  const tracks = useQuery({
    queryKey: ['tracks'],
    queryFn: async () => {
      const result = await listTracks()
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    retry: false,
  })
  const kept = useQuery({
    queryKey: ['fit-evaluations', jobId],
    queryFn: async () => {
      const result = await getJobEvaluations(jobId)
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    retry: false,
  })

  const run = useMutation({
    mutationFn: async (trackId: string) => {
      const result = await evaluateJob(jobId, trackId)
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    onSuccess: (data) => {
      client.setQueryData<Evaluation[]>(['fit-evaluations', jobId], (old) => [
        ...(old ?? []).filter((e) => e.trackId !== data.trackId),
        data,
      ])
    },
  })

  if (tracks.isPending || kept.isPending) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading the fit check"
        className="animate-pulse"
      >
        <div className="h-24 rounded-xl bg-surface-sunken" />
      </div>
    )
  }

  const loadError = tracks.error ?? kept.error
  if (loadError) {
    const code = loadError instanceof StepError ? loadError.code : 'unexpected'
    const copy = fitCopy(code === 'unexpected' ? 'unexpected' : code)
    return (
      <Problem title={copy.title} body={copy.body}>
        <button
          type="button"
          className={BTN_PRIMARY}
          onClick={() => {
            void tracks.refetch()
            void kept.refetch()
          }}
        >
          Retry
        </button>
      </Problem>
    )
  }

  const everyTrack = tracks.data
  const keptList = kept.data
  if (!everyTrack || !keptList) return null
  // A track only checks opportunities of its own type.
  const trackList = everyTrack.filter((t) => t.kind === kind)

  if (trackList.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <h3 className="font-display text-base font-bold text-ink">
          {everyTrack.length === 0
            ? 'Add a track to check fit'
            : `Add a track for this kind of work`}
        </h3>
        <p className="text-sm text-muted">
          {everyTrack.length === 0
            ? 'The fit check compares a job with one of your tracks: the roles, pay and work mode you are looking for.'
            : `This is a ${kindLabel(kind).toLowerCase()}, and a track only checks its own kind of work. Add a ${kindLabel(kind).toLowerCase()} track in your profile.`}
        </p>
        <Link to="/profile" className={BTN_PRIMARY + ' self-start'}>
          Go to your profile
        </Link>
      </div>
    )
  }

  const trackId = pickTrack(trackList, chosen)
  if (trackId === null) return null
  const track = trackList.find((t) => t.id === trackId)
  const result = evaluationFor(keptList, trackId)
  const working = run.isPending

  const error =
    run.error instanceof StepError
      ? fitCopy(run.error.code)
      : run.isError
        ? fitCopy('unexpected')
        : null

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">
        AI compares the posting with your confirmed profile. It can be wrong, so
        check it yourself.
      </p>

      {trackList.length > 1 ? (
        <label className="flex flex-wrap items-center gap-2 text-sm font-bold text-ink">
          Track
          <select
            className="min-h-11 rounded-lg border border-border bg-surface px-3 text-sm font-normal"
            value={trackId}
            onChange={(event) => {
              setChosen(event.target.value)
              run.reset()
            }}
          >
            {trackList.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p className="text-sm text-ink">
          Track: <span className="font-bold">{track?.name}</span>
        </p>
      )}

      {error ? (
        <Problem title={error.title} body={error.body}>
          {error.action === 'profile' ? (
            <Link to="/profile" className={BTN_PRIMARY}>
              Go to your profile
            </Link>
          ) : error.action === 'retry' ? (
            <button
              type="button"
              className={BTN_PRIMARY}
              disabled={working}
              onClick={() => run.mutate(trackId)}
            >
              {working ? 'Checking…' : 'Try again'}
            </button>
          ) : null}
        </Problem>
      ) : null}

      {working ? (
        <p role="status" className="text-sm font-bold text-ink">
          Checking this job against your profile. This can take a little while.
        </p>
      ) : null}

      {result === null && !working && !error ? (
        <div className="flex flex-col items-start gap-2">
          <p className="text-sm text-muted">
            Not checked yet. Checking sends the posting text to the AI model.
          </p>
          <button
            type="button"
            className={BTN_PRIMARY}
            onClick={() => run.mutate(trackId)}
          >
            Check my fit
          </button>
        </div>
      ) : null}

      {result !== null ? (
        <Result
          result={result}
          working={working}
          onRefresh={() => run.mutate(trackId)}
        />
      ) : null}
    </div>
  )
}

function Result({
  result,
  working,
  onRefresh,
}: {
  result: Evaluation
  working: boolean
  onRefresh: () => void
}) {
  const rows = checkRows(result.checks)
  const reqs = sortRequirements(result.requirements)
  return (
    <div className="flex flex-col gap-4">
      {result.stale ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface p-3 text-sm text-ink">
          <span>
            Your profile or this track changed after this check was made.
          </span>
          <button
            type="button"
            className={BTN}
            disabled={working}
            onClick={onRefresh}
          >
            {working ? 'Checking…' : 'Check again'}
          </button>
        </div>
      ) : null}

      <section
        aria-label="Fit band"
        className="rounded-xl border border-border bg-surface p-4"
      >
        <p className="text-xs font-bold uppercase tracking-wide text-muted">
          Fit band
        </p>
        <p className="font-display text-2xl font-bold text-ink">
          {bandLabel(result.band)}
        </p>
        <p className="mt-1 text-sm text-muted">{result.summary}</p>
      </section>

      {result.mainGap ? (
        <section
          aria-label="Main gap"
          className="rounded-xl border border-border bg-surface p-4"
        >
          <p className="text-xs font-bold uppercase tracking-wide text-muted">
            Main gap
          </p>
          <p className="break-words font-bold text-ink">
            {result.mainGap.need}
          </p>
          <p className="mt-1 break-words text-sm text-muted">
            <span className="font-bold">AI note: </span>
            {result.mainGap.note}
          </p>
        </section>
      ) : null}

      <ul aria-label="Checks" className="grid gap-2 sm:grid-cols-3">
        {rows.map((row) => (
          <li
            key={row.label}
            className="rounded-xl border border-border bg-surface p-3"
          >
            <p className="text-xs font-bold uppercase tracking-wide text-muted">
              {row.label}
            </p>
            <p className={`text-sm font-bold ${TONE[row.tone]}`}>
              <span aria-hidden="true">{MARK[row.tone]} </span>
              {row.value}
            </p>
            {row.note ? (
              <p className="mt-0.5 break-words text-xs text-muted">
                {row.note}
              </p>
            ) : null}
          </li>
        ))}
      </ul>

      <details className="rounded-xl border border-border bg-surface p-3">
        <summary className="min-h-11 cursor-pointer py-2 text-sm font-bold text-ink">
          Show the evidence for all {reqs.length} requirements
        </summary>
        <ul className="mt-2 flex flex-col gap-3">
          {reqs.map((r, at) => (
            <li
              key={at}
              className="border-t border-border pt-3 first:border-t-0 first:pt-0"
            >
              <p className="text-sm font-bold text-ink">
                <span aria-hidden="true">{STATUS_MARK[r.status]} </span>
                <span className="break-words">{r.need}</span>
              </p>
              <p className="text-xs text-muted">
                {statusLabel(r.status)} · {importanceLabel(r.importance)}
              </p>
              <p className="mt-1 break-words text-xs text-muted">
                From the posting: “{r.quote}”
              </p>
              {r.evidence.length > 0 ? (
                <div className="mt-1 text-xs text-ink">
                  <p className="font-bold">Your evidence:</p>
                  <ul className="list-disc pl-4">
                    {r.evidence.map((e) => (
                      <li key={`${e.kind}:${e.id}`} className="break-words">
                        {e.text}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <p className="mt-1 break-words text-xs text-muted">
                <span className="font-bold">AI note: </span>
                {r.note}
              </p>
            </li>
          ))}
        </ul>
      </details>

      {!result.stale ? (
        <button
          type="button"
          className={BTN + ' self-start'}
          disabled={working}
          onClick={onRefresh}
        >
          {working ? 'Checking…' : 'Check again'}
        </button>
      ) : null}
    </div>
  )
}
