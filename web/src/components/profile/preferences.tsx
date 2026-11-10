import { useEffect, useRef, useState } from 'react'
import { BTN, BTN_PRIMARY } from '#/components/cv/parts'
import {
  LIMITS,
  WORK_MODES,
  fromPrefsForm,
  toPrefsForm,
} from '#/lib/tracks-view'
import type { PrefsField, PrefsForm, Track, WorkMode } from '#/lib/tracks-view'

const FIELD =
  'w-full rounded-xl border border-border-strong bg-surface px-3 py-2.5 text-sm font-normal text-ink'
const LABEL = 'flex flex-col gap-1.5 text-[13px] font-bold text-muted'
const HINT = 'text-xs font-normal text-faint'

/** One count line for the closed panel: how much is filled in. */
export function summary(track: Track): string {
  const p = track.preferences
  const filled = [
    p.targetRoles.length > 0,
    p.salaryFloor !== null,
    p.workModes.length > 0,
    p.locations.length > 0,
    p.eligibility !== null,
    p.criteria.length > 0,
    p.dealbreakers.length > 0,
    p.doNotApply.length > 0,
  ].filter(Boolean).length
  return filled === 0 ? 'Nothing set yet' : `${filled} of 8 set`
}

/** The preferences form for the chosen track. Save returns an error sentence, or null. */
export function PreferencesPanel({
  track,
  busy,
  onSave,
  onClose,
}: {
  track: Track
  busy: boolean
  onSave: (body: Record<string, unknown>) => Promise<string | null>
  onClose: () => void
}) {
  const [form, setForm] = useState<PrefsForm>(() =>
    toPrefsForm(track.preferences),
  )
  const [errors, setErrors] = useState<Partial<Record<PrefsField, string>>>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const first = useRef<HTMLTextAreaElement>(null)
  useEffect(() => first.current?.focus(), [])

  const set = <TKey extends PrefsField>(key: TKey, value: PrefsForm[TKey]) => {
    setForm((current) => ({ ...current, [key]: value }))
    setErrors((current) => ({ ...current, [key]: undefined }))
  }

  const lines = (
    key: PrefsField,
    label: string,
    hint: string,
    rows = 3,
    ref?: React.Ref<HTMLTextAreaElement>,
  ) => (
    <label className={LABEL}>
      {label}
      <textarea
        ref={ref}
        rows={rows}
        value={form[key]}
        aria-invalid={errors[key] ? true : undefined}
        aria-describedby={`${key}-hint${errors[key] ? ` ${key}-err` : ''}`}
        onChange={(event) => set(key, event.target.value as never)}
        className={FIELD}
      />
      <span id={`${key}-hint`} className={HINT}>
        {hint}
      </span>
      {errors[key] && (
        <span id={`${key}-err`} className="text-xs font-bold text-bad-ink">
          {errors[key]}
        </span>
      )}
    </label>
  )

  async function submit() {
    const checked = fromPrefsForm(form, track.preferences)
    if (!checked.ok) {
      setErrors(checked.errors)
      setServerError(null)
      requestAnimationFrame(() =>
        document
          .querySelector<HTMLElement>('#prefs-form [aria-invalid="true"]')
          ?.focus(),
      )
      return
    }
    if (Object.keys(checked.body).length === 0) {
      onClose()
      return
    }
    const failure = await onSave(checked.body)
    if (failure) setServerError(failure)
  }

  return (
    <form
      id="prefs-form"
      noValidate
      aria-label={`Preferences for ${track.name}`}
      onSubmit={(event) => {
        event.preventDefault()
        void submit()
      }}
      className="flex flex-col gap-4 border-t border-surface-sunken pt-4"
    >
      <p className="text-[13px] leading-relaxed text-faint">
        All optional, one item per line. These are saved with this track; jobs
        will be checked against them once evaluation arrives.
      </p>
      {lines(
        'targetRoles',
        'What roles are you hoping to find?',
        `Up to ${LIMITS.roles.items} roles, ${LIMITS.roles.chars} characters each.`,
        3,
        first,
      )}
      <div className="grid gap-4 sm:grid-cols-[2fr_1fr]">
        <label className={LABEL}>
          Lowest salary you would consider
          <input
            type="text"
            inputMode="numeric"
            value={form.salaryFloor}
            aria-invalid={errors.salaryFloor ? true : undefined}
            aria-describedby={
              errors.salaryFloor ? 'salaryFloor-err' : undefined
            }
            onChange={(event) => set('salaryFloor', event.target.value)}
            className={`${FIELD} min-h-11`}
          />
          <span className={HINT}>A year, as a whole number.</span>
          {errors.salaryFloor && (
            <span
              id="salaryFloor-err"
              className="text-xs font-bold text-bad-ink"
            >
              {errors.salaryFloor}
            </span>
          )}
        </label>
        <label className={LABEL}>
          Currency
          <input
            type="text"
            maxLength={3}
            value={form.currency}
            aria-invalid={errors.currency ? true : undefined}
            aria-describedby={errors.currency ? 'currency-err' : undefined}
            onChange={(event) => set('currency', event.target.value)}
            className={`${FIELD} min-h-11 uppercase`}
          />
          <span className={HINT}>For example USD or KES.</span>
          {errors.currency && (
            <span id="currency-err" className="text-xs font-bold text-bad-ink">
              {errors.currency}
            </span>
          )}
        </label>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="text-[13px] font-bold text-muted">
          How can you work?
        </legend>
        <div className="flex flex-wrap gap-x-5 gap-y-1">
          {WORK_MODES.map((mode) => (
            <label
              key={mode.value}
              className="flex min-h-11 items-center gap-2 text-sm font-bold text-ink"
            >
              <input
                type="checkbox"
                checked={form.workModes.includes(mode.value)}
                onChange={(event) =>
                  set(
                    'workModes',
                    event.target.checked
                      ? [...form.workModes, mode.value]
                      : form.workModes.filter(
                          (value: WorkMode) => value !== mode.value,
                        ),
                  )
                }
                className="size-5 accent-[#B04A27]"
              />
              {mode.label}
            </label>
          ))}
        </div>
        <span className={HINT}>Leave all unticked for any.</span>
      </fieldset>
      {lines(
        'locations',
        'Where can you work?',
        `Up to ${LIMITS.locations.items} places, for example Nairobi or Remote in EMEA.`,
      )}
      {lines(
        'eligibility',
        'Anything about your right to work',
        `Visas or sponsorship, up to ${LIMITS.eligibility} characters.`,
        2,
      )}
      <div className="grid gap-4 md:grid-cols-3">
        {lines('must', 'Must have', 'A job without these is not for you.', 4)}
        {lines('important', 'Important', 'Weighs heavily in a fit.', 4)}
        {lines('nice', 'Nice to have', 'A small plus.', 4)}
      </div>
      {lines(
        'dealbreakers',
        'Anything that is a firm no?',
        `Plain sentences such as “No on-site only”. Up to ${LIMITS.dealbreakers.items}.`,
      )}
      {lines(
        'doNotApply',
        'Companies to skip',
        `One company per line, up to ${LIMITS.doNotApply.items}.`,
      )}
      {serverError && (
        <p role="alert" className="text-sm font-bold text-bad-ink">
          {serverError}
        </p>
      )}
      <div className="flex flex-wrap gap-2.5">
        <button type="submit" className={BTN_PRIMARY} disabled={busy}>
          {busy ? 'Saving…' : 'Save preferences'}
        </button>
        <button type="button" className={BTN} disabled={busy} onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  )
}
