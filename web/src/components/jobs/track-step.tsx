import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BTN, BTN_PRIMARY } from '#/components/cv/parts'
import { trackJob } from '#/lib/jobs-api'
import type { JobFull, Outcome, Stage, TrackingChange } from '#/lib/jobs-api'
import { safeHref } from '#/lib/jobs-view'
import {
  MAX_NOTES,
  OUTCOMES,
  STAGES,
  appliedNote,
  followUpNote,
  outcomeLabel,
  stageLabel,
  trackingCopy,
} from '#/lib/tracking-view'

class StepError extends Error {
  readonly code: string
  constructor(code: string) {
    super(code)
    this.code = code
  }
}

const FIELD =
  'min-h-11 rounded-lg border border-border bg-surface px-3 text-sm text-ink'

/** The Track step: where this job stands, when to follow up, how it went, and your notes. */
export function TrackStep({ job }: { job: JobFull }) {
  const client = useQueryClient()
  // null means untouched: the box then shows the saved notes.
  const [notes, setNotes] = useState<string | null>(null)
  const [asked, setAsked] = useState(false)
  const [saved, setSaved] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: async (change: TrackingChange) => {
      const result = await trackJob(job.id, change)
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    onSuccess: async (data, change) => {
      client.setQueryData(['job-workspace', job.id], data)
      if (change.notes !== undefined) setNotes(null)
      setSaved(change.notes !== undefined ? 'Notes saved.' : 'Saved.')
      await client.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: () => setSaved(null),
  })

  const notesValue = notes ?? job.notes
  const used = Array.from(notesValue).length
  const posting = safeHref(job.sourceUrl)
  const applied = appliedNote(job.appliedAt)
  const chase = followUpNote(job)
  const copy = save.error
    ? trackingCopy(
        save.error instanceof StepError ? save.error.code : 'unexpected',
      )
    : null
  const beforeApplied = job.stage === 'saved' || job.stage === 'preparing'

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">
        Keep track of this application. Nothing here is sent anywhere.
      </p>

      <label className="flex flex-wrap items-center gap-2 text-sm font-bold text-ink">
        Stage
        <select
          className={`${FIELD} font-normal`}
          value={job.stage}
          disabled={save.isPending}
          onChange={(event) =>
            save.mutate({ stage: event.target.value as Stage })
          }
        >
          {STAGES.map((stage) => (
            <option key={stage} value={stage}>
              {stageLabel(stage)}
            </option>
          ))}
        </select>
      </label>
      {applied ? <p className="text-sm text-muted">{applied}.</p> : null}

      {beforeApplied && posting ? (
        <div className="flex flex-col items-start gap-3 rounded-xl border border-border bg-surface p-4">
          <p className="text-sm text-muted">
            Jobmigo does not apply for you. Open the posting, apply with your
            downloaded CV and letter, then come back.
          </p>
          <a
            className={BTN_PRIMARY}
            href={posting}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setAsked(true)}
          >
            Open the posting and apply
          </a>
          {asked ? (
            <div
              role="group"
              aria-label="Did you apply?"
              className="flex flex-col gap-2"
            >
              <p className="text-sm font-bold text-ink">Did you apply?</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className={BTN_PRIMARY}
                  disabled={save.isPending}
                  onClick={() => {
                    save.mutate({ stage: 'applied' })
                    setAsked(false)
                  }}
                >
                  Yes, I applied
                </button>
                <button
                  type="button"
                  className={BTN}
                  onClick={() => setAsked(false)}
                >
                  Not yet
                </button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1.5 text-sm font-bold text-ink">
          Follow up on
          <input
            type="date"
            className={`${FIELD} font-normal`}
            value={job.followUpOn ?? ''}
            disabled={save.isPending}
            onChange={(event) =>
              save.mutate({ followUpOn: event.target.value || null })
            }
          />
        </label>
        {job.followUpOn ? (
          <button
            type="button"
            className={BTN}
            disabled={save.isPending}
            onClick={() => save.mutate({ followUpOn: null })}
          >
            Clear the date
          </button>
        ) : null}
      </div>
      {chase ? (
        <p
          className={`text-sm ${chase.due ? 'font-bold text-warn-ink' : 'text-muted'}`}
        >
          {chase.text}.
        </p>
      ) : null}

      <label className="flex flex-wrap items-center gap-2 text-sm font-bold text-ink">
        How it went
        <select
          className={`${FIELD} font-normal`}
          value={job.outcome ?? ''}
          disabled={save.isPending}
          onChange={(event) =>
            save.mutate({
              outcome: event.target.value
                ? (event.target.value as Outcome)
                : null,
            })
          }
        >
          <option value="">No outcome yet</option>
          {OUTCOMES.map((outcome) => (
            <option key={outcome} value={outcome}>
              {outcomeLabel(outcome)}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1.5 text-sm font-bold text-ink">
        Notes
        <textarea
          className={`${FIELD} min-h-28 py-3 font-normal`}
          value={notesValue}
          aria-describedby="track-notes-count"
          aria-invalid={used > MAX_NOTES ? true : undefined}
          onChange={(event) => {
            setNotes(event.target.value)
            setSaved(null)
          }}
        />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className={BTN}
          disabled={
            save.isPending ||
            notes === null ||
            notes === job.notes ||
            used > MAX_NOTES
          }
          onClick={() => save.mutate({ notes: notesValue })}
        >
          {save.isPending ? 'Saving…' : 'Save notes'}
        </button>
        <span id="track-notes-count" className="text-xs text-muted">
          {used > MAX_NOTES
            ? `${used} of ${MAX_NOTES} characters: over by ${used - MAX_NOTES}.`
            : `${used} of ${MAX_NOTES} characters`}
        </span>
      </div>

      {saved && !copy ? (
        <p role="status" className="text-sm font-bold text-ink">
          {saved}
        </p>
      ) : null}
      {copy ? (
        <div role="alert" className="text-sm text-ink">
          <p className="font-bold">{copy.title}</p>
          <p className="text-muted">{copy.body}</p>
        </div>
      ) : null}
    </div>
  )
}
