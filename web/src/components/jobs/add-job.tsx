import { useEffect, useRef, useState } from 'react'
import { BTN, BTN_GHOST, BTN_PRIMARY, Problem } from '#/components/cv/parts'
import { addJob, fetchJobPage } from '#/lib/jobs-api'
import type { JobFull } from '#/lib/jobs-api'
import {
  LIMITS,
  PASTE_INSTEAD,
  checkAdd,
  jobsCopy,
  readableLink,
  sourceHost,
  titleHint,
} from '#/lib/jobs-view'
import type { AddField, AddForm } from '#/lib/jobs-view'
import { OPPORTUNITY_KINDS, kindLabel } from '#/lib/opportunity'
import type { OpportunityKind } from '#/lib/opportunity'

const FIELD =
  'w-full rounded-xl border border-border-strong bg-surface px-3 text-sm font-normal text-ink'
const LABEL = 'flex flex-col gap-1.5 text-[13px] font-bold text-muted'
const HINT = 'text-xs font-normal text-faint'

type Step = 'link' | 'form'
type Failure = { code: string }

const EMPTY: AddForm = { company: '', title: '', location: '', text: '' }

/** Add a job: read a link (when the site allows it) or paste the text, then confirm and save. */
export function AddJob({
  onSaved,
  onClose,
  onUnauthorized,
}: {
  onSaved: (job: JobFull) => void
  onClose: () => void
  onUnauthorized: () => void
}) {
  const [step, setStep] = useState<Step>('link')
  const [link, setLink] = useState('')
  const [linkError, setLinkError] = useState<string | null>(null)
  const [reading, setReading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [form, setForm] = useState<AddForm>(EMPTY)
  const [kind, setKind] = useState<OpportunityKind>('job')
  const [errors, setErrors] = useState<Partial<Record<AddField, string>>>({})
  const [pageNote, setPageNote] = useState<string | null>(null)
  const [finalUrl, setFinalUrl] = useState<string | null>(null)
  const linkInput = useRef<HTMLInputElement>(null)
  const firstField = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (step === 'link') linkInput.current?.focus()
    else firstField.current?.focus()
  }, [step])

  const set = (key: keyof AddForm, value: string) => {
    setForm((current) => ({ ...current, [key]: value }))
    setErrors((current) => ({ ...current, [key]: undefined }))
  }

  async function read() {
    const value = link.trim()
    if (!readableLink(value)) {
      setLinkError('Use a full web address that starts with http or https.')
      linkInput.current?.focus()
      return
    }
    setLinkError(null)
    setFailure(null)
    setReading(true)
    const result = await fetchJobPage(value)
    setReading(false)
    if (!result.ok) {
      if (result.code === 'unauthorized') return onUnauthorized()
      setFailure({ code: result.code })
      return
    }
    setForm({
      ...EMPTY,
      title: titleHint(result.data.title),
      text: result.data.text,
    })
    setFinalUrl(result.data.finalUrl)
    setPageNote(
      result.data.truncated
        ? 'The page was long, so we kept the first part. Check it has what you need.'
        : null,
    )
    setErrors({})
    setStep('form')
  }

  function pasteInstead() {
    setFailure(null)
    setFinalUrl(readableLink(link.trim()) ? link.trim() : null)
    setPageNote(null)
    setForm(EMPTY)
    setErrors({})
    setStep('form')
  }

  async function save() {
    const checked = checkAdd(form, finalUrl, kind)
    if (!checked.ok) {
      setErrors(checked.errors)
      setFailure(null)
      requestAnimationFrame(() =>
        document
          .querySelector<HTMLElement>('#add-job-form [aria-invalid="true"]')
          ?.focus(),
      )
      return
    }
    setSaving(true)
    setFailure(null)
    const result = await addJob(checked.body)
    setSaving(false)
    if (!result.ok) {
      if (result.code === 'unauthorized') return onUnauthorized()
      setFailure({ code: result.code })
      return
    }
    onSaved(result.data)
  }

  const busy = reading || saving

  return (
    <section
      aria-labelledby="add-job-title"
      className="flex flex-col gap-4 rounded-[20px] border border-border bg-surface p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2
          id="add-job-title"
          className="font-display text-[17px] font-bold text-ink"
        >
          Add a job
        </h2>
        <button
          type="button"
          className={BTN_GHOST}
          onClick={onClose}
          disabled={busy}
        >
          Close
        </button>
      </div>

      {step === 'link' && (
        <form
          noValidate
          aria-label="Read a job link"
          onSubmit={(event) => {
            event.preventDefault()
            void read()
          }}
          className="flex flex-col gap-3"
        >
          <label className={LABEL}>
            Link to the job posting
            <input
              ref={linkInput}
              type="url"
              inputMode="url"
              value={link}
              placeholder="https://"
              aria-invalid={linkError ? true : undefined}
              aria-describedby={`link-hint${linkError ? ' link-err' : ''}`}
              onChange={(event) => {
                setLink(event.target.value)
                setLinkError(null)
              }}
              className={`${FIELD} min-h-11`}
            />
            <span id="link-hint" className={HINT}>
              We read the public page only when the site allows it. Otherwise
              you can paste the text.
            </span>
            {linkError && (
              <span id="link-err" className="text-xs font-bold text-bad-ink">
                {linkError}
              </span>
            )}
          </label>
          {reading && (
            <p role="status" className="text-sm font-bold text-muted">
              Reading the page…
            </p>
          )}
          {failure && (
            <Problem
              title={jobsCopy(failure.code).title}
              body={jobsCopy(failure.code).body}
            >
              {PASTE_INSTEAD.has(failure.code) && (
                <button
                  type="button"
                  className={BTN_PRIMARY}
                  onClick={pasteInstead}
                >
                  Paste the text instead
                </button>
              )}
            </Problem>
          )}
          <div className="flex flex-wrap gap-2.5">
            <button type="submit" className={BTN_PRIMARY} disabled={busy}>
              {reading ? 'Reading…' : 'Read the page'}
            </button>
            <button
              type="button"
              className={BTN}
              disabled={busy}
              onClick={pasteInstead}
            >
              Paste the text instead
            </button>
          </div>
        </form>
      )}

      {step === 'form' && (
        <form
          id="add-job-form"
          noValidate
          aria-label="Job details"
          onSubmit={(event) => {
            event.preventDefault()
            void save()
          }}
          className="flex flex-col gap-3.5"
        >
          {finalUrl && (
            <p className="break-words text-[13px] text-faint">
              From {sourceHost(finalUrl) ?? 'the link you gave'}
            </p>
          )}
          {pageNote && (
            <p className="text-[13px] font-bold text-body">{pageNote}</p>
          )}
          <fieldset className="flex flex-col gap-1.5">
            <legend className="text-[13px] font-bold text-muted">
              What kind of opportunity is this?
            </legend>
            <div className="flex flex-wrap gap-x-5">
              {OPPORTUNITY_KINDS.map((option) => (
                <label
                  key={option}
                  className="inline-flex min-h-11 items-center gap-2 text-sm text-ink"
                >
                  <input
                    type="radio"
                    name="opportunity-kind"
                    value={option}
                    checked={kind === option}
                    onChange={() => setKind(option)}
                  />
                  {kindLabel(option)}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="grid gap-3.5 sm:grid-cols-2">
            <label className={LABEL}>
              Company
              <input
                ref={firstField}
                type="text"
                value={form.company}
                aria-invalid={errors.company ? true : undefined}
                aria-describedby={errors.company ? 'company-err' : undefined}
                onChange={(event) => set('company', event.target.value)}
                className={`${FIELD} min-h-11`}
              />
              {errors.company && (
                <span
                  id="company-err"
                  className="text-xs font-bold text-bad-ink"
                >
                  {errors.company}
                </span>
              )}
            </label>
            <label className={LABEL}>
              Job title
              <input
                type="text"
                value={form.title}
                aria-invalid={errors.title ? true : undefined}
                aria-describedby={errors.title ? 'title-err' : undefined}
                onChange={(event) => set('title', event.target.value)}
                className={`${FIELD} min-h-11`}
              />
              {errors.title && (
                <span id="title-err" className="text-xs font-bold text-bad-ink">
                  {errors.title}
                </span>
              )}
            </label>
          </div>
          <label className={LABEL}>
            Where is the job? (optional)
            <input
              type="text"
              value={form.location}
              aria-invalid={errors.location ? true : undefined}
              aria-describedby={errors.location ? 'location-err' : undefined}
              onChange={(event) => set('location', event.target.value)}
              className={`${FIELD} min-h-11`}
            />
            {errors.location && (
              <span
                id="location-err"
                className="text-xs font-bold text-bad-ink"
              >
                {errors.location}
              </span>
            )}
          </label>
          <label className={LABEL}>
            Posting text
            <textarea
              rows={10}
              value={form.text}
              aria-invalid={errors.text ? true : undefined}
              aria-describedby={`text-hint${errors.text ? ' text-err' : ''}`}
              onChange={(event) => set('text', event.target.value)}
              className={`${FIELD} py-2.5`}
            />
            <span id="text-hint" className={HINT}>
              Plain text or a saved page, up to{' '}
              {LIMITS.textMax.toLocaleString('en-US')} characters. Hidden parts
              are removed when we save it.
            </span>
            {errors.text && (
              <span id="text-err" className="text-xs font-bold text-bad-ink">
                {errors.text}
              </span>
            )}
          </label>
          {errors.url && (
            <p className="text-xs font-bold text-bad-ink" role="alert">
              {errors.url}
            </p>
          )}
          {failure && (
            <Problem
              title={jobsCopy(failure.code).title}
              body={jobsCopy(failure.code).body}
            />
          )}
          <div className="flex flex-wrap gap-2.5">
            <button type="submit" className={BTN_PRIMARY} disabled={busy}>
              {saving ? 'Saving…' : 'Save job'}
            </button>
            <button
              type="button"
              className={BTN}
              disabled={busy}
              onClick={() => {
                setFailure(null)
                setStep('link')
              }}
            >
              Back
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
