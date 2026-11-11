import { useEffect, useRef, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BTN, BTN_PRIMARY, Problem } from '#/components/cv/parts'
import { editKit, exportKit, getKits, writeKit } from '#/lib/jobs-api'
import type { KitEdit, KitVersion } from '#/lib/jobs-api'
import {
  blockLimit,
  blocksOf,
  checkQuestions,
  checkSummary,
  docLabel,
  docsInOrder,
  factLines,
  flagWords,
  kitCopy,
  needsYou,
  preview,
  versionLabel,
} from '#/lib/kit-view'
import type { Located } from '#/lib/kit-view'
import { kindDocument, kindLabel } from '#/lib/opportunity'
import type { OpportunityKind } from '#/lib/opportunity'
import { getProfile } from '#/lib/profile-api'
import { listTracks } from '#/lib/tracks-api'
import { useMe } from '#/lib/useMe'

class StepError extends Error {
  readonly code: string
  constructor(code: string) {
    super(code)
    this.code = code
  }
}

const CARD = 'rounded-xl border border-border bg-surface p-4'
const FIELD =
  'w-full rounded-lg border border-border bg-surface p-3 text-sm text-ink'

/** The CV and letter step: the kit for one track, its fact check, and a way to fix it. */
export function KitStep({
  jobId,
  kind,
}: {
  jobId: string
  kind: OpportunityKind
}) {
  const client = useQueryClient()
  const [chosen, setChosen] = useState<string | null>(null)
  const [doc, setDoc] = useState<KitVersion['docType'] | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  // null means untouched: the box then shows the questions already answered.
  const [questions, setQuestions] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const noticeRef = useRef<HTMLParagraphElement>(null)
  const [questionError, setQuestionError] = useState<string | null>(null)

  const tracks = useQuery({
    queryKey: ['tracks'],
    queryFn: async () => {
      const result = await listTracks()
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    retry: false,
  })
  const trackList = (tracks.data ?? []).filter((t) => t.kind === kind)
  const trackId =
    chosen && trackList.some((t) => t.id === chosen)
      ? chosen
      : (trackList.at(0)?.id ?? null)

  const kits = useQuery({
    queryKey: ['kits', jobId, trackId],
    enabled: trackId !== null,
    queryFn: async () => {
      const result = await getKits(jobId, trackId ?? undefined)
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    retry: false,
  })
  const profile = useQuery({
    queryKey: ['profile'],
    queryFn: async () => {
      const result = await getProfile()
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    retry: false,
  })

  const refresh = () =>
    client.invalidateQueries({ queryKey: ['kits', jobId, trackId] })

  const write = useMutation({
    mutationFn: async (list: string[]) => {
      const result = await writeKit(jobId, trackId ?? '', list)
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    onSuccess: async () => {
      setPicked(null)
      setNotice(null)
      await refresh()
    },
  })
  const change = useMutation({
    mutationFn: async (input: { kitId: string; change: KitEdit }) => {
      const result = await editKit(jobId, input.kitId, input.change)
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    onSuccess: async (_saved, input) => {
      setPicked(null)
      setNotice(
        input.change.action === 'remove'
          ? 'Removed. This is saved as a new version.'
          : 'Saved as a new version.',
      )
      await refresh()
    },
  })

  // Say what happened, and move focus there: the statement that was changed is gone.
  useEffect(() => {
    if (notice !== null) noticeRef.current?.focus()
  }, [notice])

  if (tracks.isPending) {
    return (
      <div aria-busy="true" aria-label="Loading" className="animate-pulse">
        <div className="h-24 rounded-xl bg-surface-sunken" />
      </div>
    )
  }
  if (tracks.isError) {
    const copy = kitCopy(
      tracks.error instanceof StepError ? tracks.error.code : 'unexpected',
    )
    return (
      <Problem title={copy.title} body={copy.body}>
        <button
          type="button"
          className={BTN_PRIMARY}
          onClick={() => void tracks.refetch()}
        >
          Retry
        </button>
      </Problem>
    )
  }

  if (trackList.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <h3 className="font-display text-base font-bold text-ink">
          {tracks.data.length === 0
            ? 'Add a track to write your CV and letter'
            : 'Add a track for this kind of work'}
        </h3>
        <p className="text-sm text-muted">
          {tracks.data.length === 0
            ? 'The kit is written for one of your tracks: the roles, pay and work mode you are looking for.'
            : `This is a ${kindLabel(kind).toLowerCase()}, and a track only works on its own kind of work. Add a ${kindLabel(kind).toLowerCase()} track in your profile.`}
        </p>
        <Link to="/profile" className={BTN_PRIMARY + ' self-start'}>
          Go to your profile
        </Link>
      </div>
    )
  }

  const all = kits.data ?? []
  const latestByDoc = new Map<string, KitVersion>()
  for (const v of all) {
    const seen = latestByDoc.get(v.docType)
    if (!seen || v.version > seen.version) latestByDoc.set(v.docType, v)
  }
  const docs = docsInOrder([...latestByDoc.values()])
  const current = docs.find((d) => d.docType === doc) ?? docs.at(0) ?? null
  const versions = current
    ? all
        .filter((v) => v.docType === current.docType)
        .sort((a, b) => b.version - a.version)
    : []
  const shown =
    versions.find((v) => v.version === picked) ?? versions.at(0) ?? null
  const isLatest = shown !== null && current !== null && shown.id === current.id

  const answered = latestByDoc.get('answers')
  const questionsValue =
    questions ??
    (answered?.content.docType === 'answers'
      ? answered.content.answers.map((a) => a.question).join('\n')
      : '')

  function startWriting() {
    const checked = checkQuestions(questionsValue)
    if (!checked.ok) {
      setQuestionError(checked.error)
      return
    }
    setQuestionError(null)
    change.reset()
    write.mutate(checked.questions)
  }

  const error = write.error ?? change.error ?? kits.error
  const copy = error
    ? kitCopy(error instanceof StepError ? error.code : 'unexpected')
    : null
  const working = write.isPending
  const writeLabel = `Write my CV and ${kindDocument(kind)}`

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">
        AI writes this from the facts you confirmed. Read every line yourself
        before you use it.
      </p>

      {trackList.length > 1 ? (
        <label className="flex flex-wrap items-center gap-2 text-sm font-bold text-ink">
          Track
          <select
            className="min-h-11 rounded-lg border border-border bg-surface px-3 text-sm font-normal"
            value={trackId ?? ''}
            onChange={(event) => {
              setChosen(event.target.value)
              setDoc(null)
              setPicked(null)
              setNotice(null)
              write.reset()
              change.reset()
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
          Track: <span className="font-bold">{trackList[0].name}</span>
        </p>
      )}

      {copy ? (
        <Problem title={copy.title} body={copy.body}>
          {copy.action === 'profile' ? (
            <Link to="/profile" className={BTN_PRIMARY}>
              Go to your profile
            </Link>
          ) : copy.action === 'reload' ? (
            <button
              type="button"
              className={BTN_PRIMARY}
              onClick={() => {
                write.reset()
                change.reset()
                void refresh()
              }}
            >
              Reload
            </button>
          ) : copy.action === 'retry' ? (
            <button
              type="button"
              className={BTN_PRIMARY}
              disabled={working}
              onClick={() => {
                if (kits.isError) void kits.refetch()
                else startWriting()
              }}
            >
              {working ? 'Writing…' : 'Try again'}
            </button>
          ) : null}
        </Problem>
      ) : null}

      {working ? (
        <p role="status" className="text-sm font-bold text-ink">
          Writing from your confirmed facts. This can take a minute.
        </p>
      ) : null}

      {kits.isPending ? (
        <div aria-busy="true" aria-label="Loading" className="animate-pulse">
          <div className="h-24 rounded-xl bg-surface-sunken" />
        </div>
      ) : null}

      {!kits.isPending && !kits.isError && current === null && !working ? (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-muted">
            Not written yet. Writing sends the posting text and your confirmed
            facts to the AI model.
          </p>
          <Questions
            value={questionsValue}
            error={questionError}
            onChange={setQuestions}
          />
          <button
            type="button"
            className={BTN_PRIMARY}
            disabled={working}
            onClick={startWriting}
          >
            {writeLabel}
          </button>
        </div>
      ) : null}

      {current !== null && shown !== null ? (
        <div className="flex flex-col gap-4">
          {current.stale ? (
            <div
              className={`${CARD} flex flex-wrap items-center gap-3 text-sm`}
            >
              <span>Your profile changed after this was written.</span>
              <button
                type="button"
                className={BTN}
                disabled={working}
                onClick={startWriting}
              >
                {working ? 'Writing…' : 'Write again'}
              </button>
            </div>
          ) : null}

          <div
            role="group"
            aria-label="Documents"
            className="flex flex-wrap gap-2"
          >
            {docs.map((d) => (
              <button
                key={d.docType}
                type="button"
                aria-pressed={d.docType === current.docType}
                className={d.docType === current.docType ? BTN_PRIMARY : BTN}
                onClick={() => {
                  setDoc(d.docType)
                  setPicked(null)
                  setNotice(null)
                  change.reset()
                }}
              >
                {docLabel(d.docType)}
              </button>
            ))}
          </div>

          {versions.length > 1 ? (
            <label className="flex flex-wrap items-center gap-2 text-sm font-bold text-ink">
              Version
              <select
                className="min-h-11 rounded-lg border border-border bg-surface px-3 text-sm font-normal"
                value={shown.version}
                onChange={(event) => {
                  setPicked(Number(event.target.value))
                  setNotice(null)
                }}
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.version}>
                    {versionLabel(v.version, current.version)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {!isLatest ? (
            <p className="text-sm text-muted">
              An older version, read only. Pick the latest to change anything.
            </p>
          ) : null}

          {notice ? (
            <p
              ref={noticeRef}
              role="status"
              tabIndex={-1}
              className="text-sm font-bold text-ink"
            >
              {notice}
            </p>
          ) : null}

          <Document
            key={shown.id}
            version={shown}
            editable={isLatest && !change.isPending}
            lines={profile.data ? factLines(profile.data) : null}
            saving={change.isPending}
            saveError={
              change.error
                ? kitCopy(
                    change.error instanceof StepError
                      ? change.error.code
                      : 'unexpected',
                  ).body
                : null
            }
            onStartEdit={() => change.reset()}
            onChange={(c) => change.mutate({ kitId: shown.id, change: c })}
          />

          <ExportSection
            key={`export-${shown.id}`}
            jobId={jobId}
            version={shown}
          />

          <div className="flex flex-col gap-3 border-t border-border pt-4">
            <details>
              <summary className="min-h-11 cursor-pointer py-2 text-sm font-bold text-ink">
                Write again, with questions
              </summary>
              <div className="mt-2 flex flex-col items-start gap-3">
                <Questions
                  value={questionsValue}
                  error={questionError}
                  onChange={setQuestions}
                />
                <button
                  type="button"
                  className={BTN}
                  disabled={working}
                  onClick={startWriting}
                >
                  {working ? 'Writing…' : 'Write again'}
                </button>
              </div>
            </details>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function Questions({
  value,
  error,
  onChange,
}: {
  value: string
  error: string | null
  onChange: (value: string) => void
}) {
  return (
    <label className="flex w-full flex-col gap-1.5 text-sm font-bold text-ink">
      Application questions (optional, one per line, up to 5)
      <textarea
        className={`${FIELD} min-h-24 font-normal`}
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? 'kit-questions-err' : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? (
        <span id="kit-questions-err" className="text-xs font-bold text-bad-ink">
          {error}
        </span>
      ) : null}
    </label>
  )
}

function Document({
  version,
  editable,
  lines,
  saving,
  saveError,
  onStartEdit,
  onChange,
}: {
  version: KitVersion
  editable: boolean
  lines: Map<string, string> | null
  saving: boolean
  saveError: string | null
  onStartEdit: () => void
  onChange: (change: KitEdit) => void
}) {
  const summary = checkSummary(version)
  const needs = needsYou(version.content)
  const located = blocksOf(version.content)
  // Which statement is open for editing. This component is keyed by the version, so a
  // new version starts with nothing open and a path can never point at a moved statement.
  const [editing, setEditing] = useState<{ path: string; text: string } | null>(
    null,
  )
  const content = version.content

  const row = (item: Located) => (
    <Statement
      key={item.path}
      item={item}
      lines={lines}
      editable={editable}
      locked={editing !== null && editing.path !== item.path}
      saving={saving}
      error={editing?.path === item.path ? saveError : null}
      editing={editing?.path === item.path ? editing.text : null}
      onStart={() => {
        onStartEdit()
        setEditing({ path: item.path, text: item.block.text })
      }}
      onType={(text) => setEditing({ path: item.path, text })}
      onCancel={() => {
        setEditing(null)
        requestAnimationFrame(() =>
          document.getElementById(`edit-${item.path}`)?.focus(),
        )
      }}
      onSave={() => {
        // The editor stays open, with the typed text, until the save has worked.
        if (editing) {
          onChange({ path: item.path, action: 'edit', text: editing.text })
        }
      }}
      onRemove={() => onChange({ path: item.path, action: 'remove' })}
    />
  )
  const byPath = new Map(located.map((l) => [l.path, l]))
  const summaryItem = byPath.get('summary')

  return (
    <div className="flex flex-col gap-4">
      <section
        aria-label="Fact check"
        className={`${CARD} flex flex-col gap-1`}
      >
        <p className="text-sm font-bold text-ink">{summary.traced}</p>
        {summary.needs ? (
          <p className="text-sm font-bold text-ink">{summary.needs}</p>
        ) : null}
        {summary.omitted ? (
          <p className="text-xs text-muted">{summary.omitted}</p>
        ) : null}
        <p className="text-xs text-muted">
          This checks that each statement cites a fact you confirmed and keeps
          its numbers. It cannot tell whether the wording is true, so read it
          yourself.
        </p>
        {needs.length > 0 ? (
          <ul className="mt-1 flex flex-col gap-1">
            {needs.map((n) => {
              const first = n.block.flags.at(0)
              return (
                <li key={n.path} className="text-sm text-ink">
                  <button
                    type="button"
                    className="min-h-11 text-left font-bold text-accent-soft-ink underline-offset-2 hover:underline"
                    onClick={() =>
                      document
                        .getElementById(`statement-${n.path}`)
                        ?.scrollIntoView({ block: 'center' })
                    }
                  >
                    {n.where}
                  </button>
                  : {first ? flagWords(first, n.block.numbers) : ''}
                </li>
              )
            })}
          </ul>
        ) : null}
      </section>

      {version.factCheck.edited.length > 0 ? (
        <p className="text-xs text-muted">
          You edited {version.factCheck.edited.length}{' '}
          {version.factCheck.edited.length === 1 ? 'statement' : 'statements'}{' '}
          in this version. Edits are checked the same way.
        </p>
      ) : null}

      {content.docType === 'cv' ? (
        <div className="flex flex-col gap-4">
          <section aria-label="Summary">
            {summaryItem ? row(summaryItem) : null}
          </section>
          {content.entries.map((entry, e) => (
            <section key={`${entry.source.id}-${e}`} aria-label={entry.heading}>
              <h3 className="break-words font-display text-base font-bold text-ink">
                {entry.heading}
              </h3>
              <ul className="mt-2 flex flex-col gap-2">
                {entry.bullets.map((_, b) => {
                  const item = byPath.get(`entries.${e + 1}.bullets.${b + 1}`)
                  return item ? <li key={item.path}>{row(item)}</li> : null
                })}
              </ul>
            </section>
          ))}
          {content.skills.length > 0 ? (
            <section aria-label="Skills">
              <h3 className="font-display text-base font-bold text-ink">
                Skills
              </h3>
              <ul className="mt-1 flex flex-wrap gap-2">
                {content.skills.map((skill, n) => (
                  <li
                    key={skill.id}
                    className="flex items-center gap-1 rounded-full border border-border px-3 text-sm text-ink"
                  >
                    <span className="break-words">{skill.name}</span>
                    {editable && editing === null ? (
                      <button
                        type="button"
                        className="min-h-11 px-2 text-xs font-bold text-accent-soft-ink"
                        aria-label={`Remove skill ${skill.name}`}
                        disabled={saving}
                        onClick={() =>
                          onChange({
                            path: `skills.${n + 1}`,
                            action: 'remove',
                          })
                        }
                      >
                        Remove
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : (
        <ol className="flex flex-col gap-3">
          {located.map((item) => (
            <li key={item.path}>
              {content.docType === 'answers' ? (
                <p className="mb-1 break-words text-sm font-bold text-ink">
                  {item.where}
                </p>
              ) : null}
              {row(item)}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function Statement({
  item,
  lines,
  editable,
  locked,
  saving,
  error,
  editing,
  onStart,
  onType,
  onCancel,
  onSave,
  onRemove,
}: {
  item: Located
  lines: Map<string, string> | null
  editable: boolean
  /** Another statement is open for editing: nothing here can be changed meanwhile. */
  locked: boolean
  saving: boolean
  error: string | null
  editing: string | null
  onStart: () => void
  onType: (text: string) => void
  onCancel: () => void
  onSave: () => void
  onRemove: () => void
}) {
  const { block } = item
  const flagged = block.flags.length > 0
  const limit = blockLimit(item.path)
  const open = editing !== null
  const box = useRef<HTMLTextAreaElement>(null)
  // Move focus into the box when it opens, so a keyboard user can type at once.
  useEffect(() => {
    if (open) box.current?.focus()
  }, [open])
  const name = `${item.where}: ${preview(block.text)}`
  return (
    <div
      id={`statement-${item.path}`}
      className={`rounded-lg border p-3 ${flagged ? 'border-warn-ink bg-warn-bg' : 'border-border bg-surface'}`}
    >
      {editing !== null ? (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1.5 text-xs font-bold text-muted">
            Edit this statement
            <textarea
              ref={box}
              className={`${FIELD} min-h-24 font-normal`}
              value={editing}
              maxLength={limit}
              aria-describedby={`count-${item.path}`}
              onChange={(event) => onType(event.target.value)}
            />
          </label>
          <p
            id={`count-${item.path}`}
            className="text-xs font-normal text-muted"
          >
            {editing.length} of {limit} characters
          </p>
          {error ? (
            <p role="alert" className="text-xs font-bold text-bad-ink">
              {error} Your text is still here.
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={BTN_PRIMARY}
              disabled={saving || editing.trim() === ''}
              onClick={onSave}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              className={BTN}
              disabled={saving}
              onClick={onCancel}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <p className="whitespace-pre-line break-words text-sm text-ink">
            {block.text || '(empty)'}
          </p>
          {block.edited ? (
            <p className="mt-1 text-xs text-muted">Edited by you</p>
          ) : null}
          {flagged ? (
            <ul className="mt-2 flex flex-col gap-0.5" aria-label="Needs you">
              {block.flags.map((f) => (
                <li key={f} className="text-xs font-bold text-warn-ink">
                  {flagWords(f, block.numbers)}
                </li>
              ))}
            </ul>
          ) : null}
          {block.sources.length > 0 ? (
            <details className="mt-2">
              <summary className="min-h-11 cursor-pointer py-2 text-xs font-bold text-muted">
                Show the facts behind it
              </summary>
              <ul className="list-disc pl-4 text-xs text-ink">
                {block.sources.map((s) => (
                  <li key={s.id} className="break-words">
                    {lines
                      ? (lines.get(s.id) ??
                        'A fact that is no longer in your profile')
                      : 'Loading…'}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
          {editable ? (
            <div className="mt-1 flex flex-wrap gap-2">
              <button
                type="button"
                id={`edit-${item.path}`}
                className={BTN}
                disabled={locked || saving}
                aria-label={`Edit ${name}`}
                onClick={onStart}
              >
                Edit
              </button>
              {item.canRemove ? (
                <button
                  type="button"
                  className={BTN}
                  disabled={locked || saving}
                  aria-label={`Remove ${name}`}
                  onClick={onRemove}
                >
                  Remove
                </button>
              ) : null}
            </div>
          ) : null}
        </>
      )}
    </div>
  )
}

/** Save a file the browser holds in memory. */
function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const NAME_MAX = 80
const CONTACT_MAX = 200

/** Download the shown version as a PDF or a DOCX. The file is made now and not stored. */
function ExportSection({
  jobId,
  version,
}: {
  jobId: string
  version: KitVersion
}) {
  const me = useMe()
  const account = me.data?.ok ? me.data.me : null
  // null means untouched: the field then shows what the account already says.
  const [name, setName] = useState<string | null>(null)
  const [contact, setContact] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)
  const nameValue = name ?? account?.displayName ?? ''
  const contactValue = contact ?? account?.email ?? ''

  const download = useMutation({
    mutationFn: async (format: 'pdf' | 'docx') => {
      const result = await exportKit(jobId, version.id, {
        format,
        name: nameValue.trim(),
        ...(contactValue.trim() ? { contact: contactValue.trim() } : {}),
      })
      if (!result.ok) throw new StepError(result.code)
      return result.data
    },
    onSuccess: (file) => saveFile(file.blob, file.filename),
  })

  function start(format: 'pdf' | 'docx') {
    const trimmed = nameValue.trim()
    if (trimmed === '') {
      setFieldError('Add the name for the document.')
      return
    }
    if (trimmed.length > NAME_MAX || contactValue.trim().length > CONTACT_MAX) {
      setFieldError(
        `Keep the name to ${NAME_MAX} characters and the contact line to ${CONTACT_MAX}.`,
      )
      return
    }
    setFieldError(null)
    download.mutate(format)
  }

  const refusal = download.error
    ? kitCopy(
        download.error instanceof StepError
          ? download.error.code
          : 'unexpected',
      )
    : null

  return (
    <section
      aria-labelledby="kit-download"
      className={`${CARD} flex flex-col gap-3`}
    >
      <div>
        <h3
          id="kit-download"
          className="font-display text-base font-bold text-ink"
        >
          Download
        </h3>
        <p className="mt-1 text-xs text-muted">
          The file is made when you ask and is not stored. The name and contact
          line are yours: they are not checked. It is checked against your
          confirmed facts again first.
        </p>
      </div>
      <label className="flex flex-col gap-1.5 text-sm font-bold text-ink">
        Name on the document
        <input
          type="text"
          className={`${FIELD} font-normal`}
          value={nameValue}
          maxLength={NAME_MAX}
          autoComplete="name"
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-bold text-ink">
        Contact line (optional)
        <input
          type="text"
          className={`${FIELD} font-normal`}
          value={contactValue}
          maxLength={CONTACT_MAX}
          placeholder="email · phone · city"
          onChange={(event) => setContact(event.target.value)}
        />
      </label>
      {fieldError ? (
        <p role="alert" className="text-xs font-bold text-bad-ink">
          {fieldError}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={BTN_PRIMARY}
          disabled={download.isPending}
          onClick={() => start('pdf')}
        >
          {download.isPending && download.variables === 'pdf'
            ? 'Making the PDF…'
            : 'Download PDF'}
        </button>
        <button
          type="button"
          className={BTN}
          disabled={download.isPending}
          onClick={() => start('docx')}
        >
          {download.isPending && download.variables === 'docx'
            ? 'Making the DOCX…'
            : 'Download DOCX'}
        </button>
      </div>
      {download.isSuccess ? (
        <p role="status" className="text-sm font-bold text-ink">
          Downloaded {download.data.filename}.
        </p>
      ) : null}
      {refusal ? (
        <div role="alert" className="text-sm text-ink">
          <p className="font-bold">{refusal.title}</p>
          <p className="text-muted">{refusal.body}</p>
        </div>
      ) : null}
    </section>
  )
}
