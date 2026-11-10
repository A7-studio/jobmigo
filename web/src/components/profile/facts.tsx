import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { BTN, BTN_GHOST, BTN_PRIMARY } from '#/components/cv/parts'
import {
  FIELDS,
  STATUS_LABEL,
  copyFor,
  datesLabel,
  fromForm,
  toForm,
} from '#/lib/profile-view'
import type {
  Achievement,
  Education,
  Experience,
  Fact,
  FormValues,
  Kind,
  Project,
  Skill,
} from '#/lib/profile-view'
import { confirmItem, deleteItem, patchItem } from '#/lib/profile-api'
import type { Result } from '#/lib/profile-api'

/** What a fact row needs from the page: one mutation at a time, and a way to run it. */
export type Ctx = {
  busy: boolean
  /**
   * Run one change. The caller shows a failure where it happened (in the form or the
   * row); only `not_found` and an ended session are handled by the page.
   */
  run: <T>(
    action: () => Promise<Result<T>>,
    done: string,
    focusSection?: Kind,
  ) => Promise<Result<T>>
  experiences: Experience[]
}

const INPUT =
  'min-h-11 w-full rounded-xl border border-border-strong bg-surface px-3 text-sm text-ink aria-[invalid=true]:border-alert'

export function StatusPill({ status }: { status: Fact['status'] }) {
  const unconfirmed = status === 'extracted'
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-xs font-bold ${
        unconfirmed
          ? 'bg-warn-bg text-warn-ink'
          : status === 'edited'
            ? 'bg-info-bg text-info-ink'
            : 'bg-good-bg text-good-ink'
      }`}
    >
      {STATUS_LABEL[status]}
    </span>
  )
}

function EditIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4" />
    </svg>
  )
}

function Field({
  field,
  values,
  error,
  set,
  idBase,
  experiences,
}: {
  field: (typeof FIELDS)[Kind][number]
  values: FormValues
  error: string | undefined
  set: (key: string, value: string | boolean) => void
  idBase: string
  experiences: Experience[]
}) {
  const id = `${idBase}-${field.key}`
  const describedBy = [error ? `${id}-err` : '', field.hint ? `${id}-hint` : '']
    .filter(Boolean)
    .join(' ')
  const common = {
    id,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': describedBy || undefined,
  }
  const value = values[field.key]
  if (field.type === 'checkbox') {
    return (
      <label className="flex min-h-11 items-center gap-2.5 text-sm text-ink">
        <input
          type="checkbox"
          checked={value === true}
          onChange={(event) => set(field.key, event.target.checked)}
          className="size-5 accent-accent-strong"
        />
        {field.label}
      </label>
    )
  }
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-bold text-muted">
        {field.label}
        {field.required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {field.type === 'textarea' ? (
        <textarea
          {...common}
          rows={4}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => set(field.key, event.target.value)}
          className={`${INPUT} py-2.5`}
        />
      ) : field.type === 'experience' ? (
        <select
          {...common}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => set(field.key, event.target.value)}
          className={INPUT}
        >
          <option value="">None</option>
          {experiences.map((job) => (
            <option key={job.id} value={job.id}>
              {job.role} at {job.company}
            </option>
          ))}
        </select>
      ) : (
        <input
          {...common}
          type="text"
          value={typeof value === 'string' ? value : ''}
          autoComplete="off"
          onChange={(event) => set(field.key, event.target.value)}
          className={INPUT}
        />
      )}
      {field.hint && (
        <p id={`${id}-hint`} className="text-xs text-faint">
          {field.hint}
        </p>
      )}
      {error && (
        <p id={`${id}-err`} className="text-xs font-bold text-bad-ink">
          {error}
        </p>
      )}
    </div>
  )
}

/** An add or edit form for one fact. */
export function FactEditor({
  kind,
  fact,
  ctx,
  onDone,
  onCancel,
  serverError,
}: {
  kind: Kind
  fact: Fact | null
  ctx: Ctx
  onDone: (values: FormValues) => Promise<boolean>
  onCancel: () => void
  serverError: string | null
}) {
  const idBase = useId()
  const [values, setValues] = useState<FormValues>(() => toForm(kind, fact))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const first = useRef<HTMLDivElement>(null)

  useEffect(() => {
    first.current
      ?.querySelector<HTMLElement>('input:not([type=checkbox]),textarea,select')
      ?.focus()
  }, [])

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        const checked = fromForm(kind, values, fact)
        if (!checked.ok) {
          setErrors(checked.errors)
          return
        }
        setErrors({})
        void onDone(values)
      }}
      className="flex flex-col gap-3.5"
    >
      <div ref={first} className="flex flex-col gap-3.5">
        {FIELDS[kind].map((field) => (
          <Field
            key={field.key}
            field={field}
            values={values}
            error={errors[field.key]}
            set={(key, value) => setValues((old) => ({ ...old, [key]: value }))}
            idBase={idBase}
            experiences={ctx.experiences}
          />
        ))}
      </div>
      {serverError && (
        <p role="alert" className="text-sm font-bold text-bad-ink">
          {serverError}
        </p>
      )}
      <div className="flex flex-wrap gap-2.5">
        <button type="submit" className={BTN_PRIMARY} disabled={ctx.busy}>
          {ctx.busy ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          className={BTN}
          disabled={ctx.busy}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

function titleOf(kind: Kind, fact: Fact, experiences: Experience[]) {
  switch (kind) {
    case 'experience':
      return {
        title: (fact as Experience).role,
        sub: experienceSub(fact as Experience),
      }
    case 'skill':
      return { title: (fact as Skill).name, sub: '' }
    case 'achievement': {
      const a = fact as Achievement
      const job = experiences.find((e) => e.id === a.experienceId)
      return {
        title: a.text,
        sub: job ? `${job.role} at ${job.company}` : '',
      }
    }
    case 'project':
      return {
        title: (fact as Project).name,
        sub: (fact as Project).description ?? '',
      }
    case 'education': {
      const e = fact as Education
      return {
        title: e.institution,
        sub: [e.qualification, datesLabel(e.start, e.end, false)]
          .filter(Boolean)
          .join(' · '),
      }
    }
  }
}

function experienceSub(job: Experience) {
  return [job.company, datesLabel(job.start, job.end, job.isCurrent)]
    .filter(Boolean)
    .join(' · ')
}

/** One fact: its text, state, and the actions that change it. */
export function FactRow({
  kind,
  fact,
  ctx,
  onClose,
  autoOpen,
}: {
  kind: Kind
  fact: Fact
  ctx: Ctx
  /** Present on the skill panel: closes it. */
  onClose?: () => void
  autoOpen?: boolean
}) {
  const [editing, setEditing] = useState(autoOpen === true)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [rowError, setRowError] = useState<string | null>(null)
  const editButton = useRef<HTMLButtonElement>(null)
  const keep = useRef<HTMLButtonElement>(null)
  const ask = useRef<HTMLButtonElement>(null)
  const wasConfirming = useRef(false)
  const wasEditing = useRef(false)

  // Focus follows the swap: into the delete question on its safe choice, and back
  // to the button that opened the editor or the question.
  useEffect(() => {
    if (confirmDelete) {
      wasConfirming.current = true
      keep.current?.focus()
    } else if (wasConfirming.current) {
      wasConfirming.current = false
      ask.current?.focus()
    }
  }, [confirmDelete])
  useEffect(() => {
    if (editing) wasEditing.current = true
    else if (wasEditing.current) {
      wasEditing.current = false
      editButton.current?.focus()
    }
  }, [editing])

  const { title, sub } = titleOf(kind, fact, ctx.experiences)
  const bullets = kind === 'experience' ? (fact as Experience).bullets : []
  const mutate = (
    action: () => Promise<Result<unknown>>,
    done: string,
    section?: Kind,
  ) => ctx.run(action, done, section)

  async function save(values: FormValues): Promise<boolean> {
    const checked = fromForm(kind, values, fact)
    if (!checked.ok) return false
    if (Object.keys(checked.body).length === 0) {
      setEditing(false)
      return true
    }
    const result = await mutate(
      () => patchItem(kind, fact.id, checked.body),
      'Saved.',
    )
    if (result.ok) {
      setServerError(null)
      setEditing(false)
      return true
    }
    setServerError(copyFor(result.code).body)
    return false
  }

  const actions = (
    <div className="flex flex-wrap items-center gap-2">
      <StatusPill status={fact.status} />
      {fact.status === 'extracted' && (
        <button
          type="button"
          className={BTN}
          disabled={ctx.busy}
          aria-label={`Confirm ${title}`}
          onClick={async () => {
            setRowError(null)
            const result = await mutate(
              () => confirmItem(kind, fact.id),
              'Confirmed.',
            )
            if (result.ok) {
              // The Confirm button is gone now; keep focus on this fact.
              requestAnimationFrame(() => editButton.current?.focus())
            } else setRowError(copyFor(result.code).body)
          }}
        >
          Confirm
        </button>
      )}
      {!editing && (
        <button
          ref={editButton}
          type="button"
          className="inline-flex size-11 items-center justify-center rounded-xl text-muted hover:bg-surface-sunken hover:text-ink"
          aria-label={`Edit ${title}`}
          disabled={ctx.busy}
          onClick={() => {
            setServerError(null)
            setEditing(true)
          }}
        >
          <EditIcon />
        </button>
      )}
    </div>
  )

  return (
    <div className="flex flex-col gap-3 border-t border-surface-sunken px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <div className="break-words text-[15px] font-extrabold text-ink">
            {title}
          </div>
          {sub && (
            <div className="mt-0.5 break-words text-[13px] text-faint">
              {sub}
            </div>
          )}
        </div>
        {actions}
      </div>

      {rowError && (
        <p role="alert" className="text-sm font-bold text-bad-ink">
          {rowError}
        </p>
      )}

      {!editing && bullets.length > 0 && (
        <ul className="m-0 list-disc pl-5 text-sm leading-relaxed text-body">
          {bullets.map((point, index) => (
            <li key={`${index}-${point}`} className="break-words">
              {point}
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <FactEditor
          kind={kind}
          fact={fact}
          ctx={ctx}
          serverError={serverError}
          onDone={save}
          onCancel={() => setEditing(false)}
        />
      )}

      {!editing && (
        <div className="flex flex-wrap items-center gap-2.5">
          {confirmDelete ? (
            <div
              role="group"
              aria-label={`Delete ${title}`}
              className="flex flex-wrap items-center gap-2.5 text-[13px] text-muted"
            >
              <span>Delete this? This cannot be undone.</span>
              <button
                type="button"
                className="inline-flex min-h-11 items-center rounded-full bg-bad-bg px-4 text-sm font-bold text-bad-ink hover:brightness-95 disabled:opacity-60"
                disabled={ctx.busy}
                onClick={async () => {
                  setRowError(null)
                  const result = await mutate(
                    () => deleteItem(kind, fact.id),
                    'Deleted.',
                    kind,
                  )
                  if (result.ok) onClose?.()
                  else {
                    setConfirmDelete(false)
                    setRowError(copyFor(result.code).body)
                  }
                }}
              >
                {ctx.busy ? 'Deleting…' : 'Delete'}
              </button>
              <button
                ref={keep}
                type="button"
                className={BTN}
                disabled={ctx.busy}
                onClick={() => setConfirmDelete(false)}
              >
                Keep it
              </button>
            </div>
          ) : (
            <button
              ref={ask}
              type="button"
              className={BTN_GHOST}
              disabled={ctx.busy}
              aria-label={`Delete ${title}`}
              onClick={() => setConfirmDelete(true)}
            >
              Delete
            </button>
          )}
          {onClose && (
            <button type="button" className={BTN} onClick={onClose}>
              Close
            </button>
          )}
        </div>
      )}
    </div>
  )
}

/** A section card with a heading that can take focus, its rows and an Add form. */
export function Section({
  kind,
  title,
  note,
  ctx,
  children,
  adding,
  setAdding,
  addError,
  onAdd,
  addLabel,
}: {
  kind: Kind
  title: string
  note?: ReactNode
  ctx: Ctx
  children: ReactNode
  adding: boolean
  setAdding: (open: boolean) => void
  addError: string | null
  onAdd: (values: FormValues) => Promise<boolean>
  addLabel: string
}) {
  const addButton = useRef<HTMLButtonElement>(null)
  const wasAdding = useRef(false)
  useEffect(() => {
    if (adding) wasAdding.current = true
    else if (wasAdding.current) {
      wasAdding.current = false
      addButton.current?.focus()
    }
  }, [adding])

  return (
    <section
      aria-labelledby={`sec-${kind}`}
      className="rise rounded-[20px] border border-border bg-surface pb-3 pt-6"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-4 pb-3.5">
        <h2
          id={`sec-${kind}`}
          tabIndex={-1}
          className="font-display text-lg font-bold tracking-tight text-ink"
        >
          {title}
        </h2>
        {note && <span className="text-xs text-faint">{note}</span>}
      </div>
      {children}
      <div className="border-t border-surface-sunken px-4 pb-1 pt-4">
        {adding ? (
          <FactEditor
            kind={kind}
            fact={null}
            ctx={ctx}
            serverError={addError}
            onDone={onAdd}
            onCancel={() => setAdding(false)}
          />
        ) : (
          <button
            ref={addButton}
            type="button"
            className={BTN}
            disabled={ctx.busy}
            onClick={() => setAdding(true)}
          >
            {addLabel}
          </button>
        )}
      </div>
    </section>
  )
}
