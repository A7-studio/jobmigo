import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BTN, BTN_PRIMARY, Problem } from '#/components/cv/parts'
import { FitStep } from '#/components/jobs/fit-step'
import { KitStep } from '#/components/jobs/kit-step'
import { STEPS, nextStep } from '#/lib/app-nav'
import type { Step } from '#/lib/app-nav'
import { getJob, setJobKind } from '#/lib/jobs-api'
import { jobsCopy } from '#/lib/jobs-view'
import { OPPORTUNITY_KINDS, isKind, kindLabel } from '#/lib/opportunity'

class LoadError extends Error {
  readonly code: string
  constructor(code: string) {
    super(code)
    this.code = code
  }
}

/** What each step will hold. Nothing here is a result: these steps are not built yet. */
const WILL_HOLD: Record<Step, string> = {
  Fit: 'how this job lines up with your approved profile, with the evidence for each point.',
  'CV and letter':
    'a CV and cover letter written for this job from your profile, with a check that each statement traces back to it.',
  Outreach:
    'people to contact for this job and a draft message that you edit and send yourself.',
  Track:
    'the stage of this application, its dates, your notes and a follow-up date.',
}

const BACK =
  'inline-flex min-h-11 items-center text-sm font-bold text-accent-soft-ink underline-offset-2 hover:underline'

/** One job: its header and the four steps. The steps are placeholders until later features. */
export function JobWorkspace({ jobId }: { jobId: string }) {
  const navigate = useNavigate()
  const client = useQueryClient()
  const [step, setStep] = useState<Step>('Fit')
  const tabs = useRef<Partial<Record<Step, HTMLButtonElement | null>>>({})

  const query = useQuery({
    queryKey: ['job-workspace', jobId],
    queryFn: async () => {
      const result = await getJob(jobId)
      if (!result.ok) throw new LoadError(result.code)
      return result.data
    },
    retry: false,
  })
  const changeKind = useMutation({
    mutationFn: async (kind: Parameters<typeof setJobKind>[1]) => {
      const result = await setJobKind(jobId, kind)
      if (!result.ok) throw new LoadError(result.code)
      return result.data
    },
    onSuccess: (data) => {
      client.setQueryData(['job-workspace', jobId], data)
      // Results for tracks of another kind are hidden, so the Fit step reads again.
      void client.invalidateQueries({ queryKey: ['fit-evaluations', jobId] })
      void client.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
  const code = query.error instanceof LoadError ? query.error.code : null
  const unauthorized = code === 'unauthorized'
  useEffect(() => {
    if (unauthorized) void navigate({ to: '/sign-in' })
  }, [unauthorized, navigate])

  if (query.isPending || unauthorized) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading this job"
        className="mx-auto max-w-[880px] animate-pulse"
      >
        <div className="h-9 w-2/3 rounded-md bg-surface-sunken" />
        <div className="mt-4 h-40 rounded-2xl bg-surface-sunken" />
      </div>
    )
  }

  if (query.isError) {
    const missing = code === 'not_found'
    return (
      <div className="mx-auto flex max-w-[880px] flex-col gap-3">
        <Link to="/jobs" className={BACK}>
          Back to jobs
        </Link>
        <Problem
          title={
            missing
              ? 'We could not find this job'
              : 'We could not load this job'
          }
          body={
            missing
              ? 'It may have been deleted, or the address is wrong.'
              : jobsCopy(code ?? 'unexpected').body
          }
        >
          {missing ? (
            <Link to="/jobs" className={BTN_PRIMARY}>
              Go to your jobs
            </Link>
          ) : (
            <button
              type="button"
              className={BTN_PRIMARY}
              disabled={query.isFetching}
              onClick={() => void query.refetch()}
            >
              {query.isFetching ? 'Retrying…' : 'Retry'}
            </button>
          )}
        </Problem>
      </div>
    )
  }

  const job = query.data

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const next = nextStep(step, event.key)
    if (!next) return
    event.preventDefault()
    setStep(next)
    tabs.current[next]?.focus()
  }

  return (
    <div className="mx-auto flex w-full max-w-[880px] flex-col gap-5">
      <Link to="/jobs" className={BACK}>
        Back to jobs
      </Link>

      <header>
        <h1 className="break-words font-display text-[28px] font-bold tracking-tight text-ink">
          {job.title}
        </h1>
        <p className="mt-1.5 break-words text-sm text-muted">
          {job.company}
          {job.location ? ` · ${job.location}` : ''}
        </p>
        <label className="mt-3 flex flex-wrap items-center gap-2 text-sm font-bold text-ink">
          Type
          <select
            className="min-h-11 rounded-lg border border-border bg-surface px-3 text-sm font-normal"
            value={job.kind}
            disabled={changeKind.isPending}
            onChange={(event) => {
              const next = event.target.value
              if (isKind(next)) changeKind.mutate(next)
            }}
          >
            {OPPORTUNITY_KINDS.map((option) => (
              <option key={option} value={option}>
                {kindLabel(option)}
              </option>
            ))}
          </select>
        </label>
        {changeKind.isError ? (
          <p role="alert" className="mt-1 text-xs font-bold text-bad-ink">
            We could not change the type. Nothing changed.
          </p>
        ) : null}
      </header>

      <div className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-4">
        <div
          role="tablist"
          aria-label="Steps for this job"
          className="flex flex-wrap gap-2"
          onKeyDown={onKeyDown}
        >
          {STEPS.map((name) => (
            <button
              key={name}
              ref={(node) => {
                tabs.current[name] = node
              }}
              type="button"
              role="tab"
              id={`tab-${name}`}
              aria-selected={step === name}
              aria-controls="step-panel"
              tabIndex={step === name ? 0 : -1}
              className={step === name ? BTN_PRIMARY : BTN}
              onClick={() => setStep(name)}
            >
              {name}
            </button>
          ))}
        </div>

        <div
          role="tabpanel"
          id="step-panel"
          aria-labelledby={`tab-${step}`}
          className="rounded-xl bg-surface-muted p-4"
        >
          <h2 className="font-display text-lg font-bold text-ink">{step}</h2>
          {step === 'Fit' ? (
            <div className="mt-2">
              <FitStep jobId={jobId} kind={job.kind} />
            </div>
          ) : step === 'CV and letter' ? (
            <div className="mt-2">
              <KitStep jobId={jobId} kind={job.kind} />
            </div>
          ) : (
            <p className="mt-1 text-sm text-muted">
              This step is not built yet. It will hold {WILL_HOLD[step]}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
