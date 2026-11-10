import { useEffect, useRef, useState } from 'react'
import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BTN,
  BTN_GHOST,
  BTN_PRIMARY,
  MigoSays,
  Problem,
} from '#/components/cv/parts'
import { FactRow, Section } from '#/components/profile/facts'
import { TracksSection } from '#/components/profile/tracks'
import type { Ctx } from '#/components/profile/facts'
import {
  addItem,
  confirmAll,
  getProfile,
  patchProfile,
} from '#/lib/profile-api'
import type { Result } from '#/lib/profile-api'
import {
  createTrack,
  deleteTrack,
  listTracks,
  patchPreferences,
  renameTrack,
  setEmphasis,
} from '#/lib/tracks-api'
import { isEmphasised, trackCopy } from '#/lib/tracks-view'
import type { Track } from '#/lib/tracks-view'
import {
  KINDS,
  LIST_KEY,
  SECTION_TITLE,
  STATUS_LABEL,
  copyFor,
  fromForm,
  progress,
} from '#/lib/profile-view'
import type { Fact, FormValues, Kind, Profile } from '#/lib/profile-view'

export const Route = createFileRoute('/_app/profile')({
  head: () => ({ meta: [{ title: 'Career profile | Jobmigo' }] }),
  component: ProfilePage,
})

class LoadError extends Error {
  readonly code: string
  constructor(code: string) {
    super(code)
    this.code = code
  }
}

const NOTE: Partial<Record<Kind, string>> = {
  experience: 'Extracted from your CV. Edit anything that looks wrong.',
  skill: 'Solid outline: confirmed or edited. Dashed outline: unconfirmed.',
}
const ADD_LABEL: Record<Kind, string> = {
  experience: 'Add a role',
  skill: 'Add a skill',
  achievement: 'Add an achievement',
  project: 'Add a project',
  education: 'Add education',
}

function ProfilePage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const announced = useRef(0)
  const titleRef = useRef<HTMLHeadingElement>(null)
  // A repeated message is changed invisibly so a screen reader says it again.
  const announce = (message: string) => {
    announced.current += 1
    setNotice(message + (announced.current % 2 === 0 ? '\u200b' : ''))
  }
  const [problem, setProblem] = useState<{
    title: string
    body: string
  } | null>(null)
  const [adding, setAdding] = useState<Kind | null>(null)
  const [addError, setAddError] = useState<string | null>(null)
  const [openSkill, setOpenSkill] = useState<string | null>(null)
  const [editingText, setEditingText] = useState(false)

  const query = useQuery({
    queryKey: ['profile'],
    queryFn: async (): Promise<Profile> => {
      const result = await getProfile()
      if (!result.ok) throw new LoadError(result.code)
      return result.data
    },
    retry: false,
  })

  const tracksQuery = useQuery({
    queryKey: ['tracks'],
    queryFn: async (): Promise<Track[]> => {
      const result = await listTracks()
      if (!result.ok) throw new LoadError(result.code)
      return result.data
    },
    retry: false,
  })
  const tracks = tracksQuery.isError ? [] : (tracksQuery.data ?? [])
  const [trackId, setTrackId] = useState<string | null>(null)
  const chosen = tracks.find((t) => t.id === trackId) ?? null

  const loadCode = query.error instanceof LoadError ? query.error.code : null
  const unauthorized = loadCode === 'unauthorized'
  useEffect(() => {
    if (unauthorized) void navigate({ to: '/sign-in' })
  }, [unauthorized, navigate])

  // After a failed read, show the error and no facts: stale values must not be edited.
  const profile = query.isError ? undefined : query.data
  const ctx: Ctx = {
    busy,
    experiences: profile?.experiences ?? [],
    async run<T>(
      action: () => Promise<Result<T>>,
      done: string,
      focusSection?: Kind,
    ) {
      setProblem(null)
      setBusy(true)
      try {
        const result = await action()
        if (result.ok) {
          announce(done)
          await queryClient.invalidateQueries({ queryKey: ['profile'] })
          if (focusSection) {
            requestAnimationFrame(() =>
              document.getElementById(`sec-${focusSection}`)?.focus(),
            )
          }
        } else if (result.code === 'unauthorized') {
          void navigate({ to: '/sign-in' })
        } else {
          if (result.code === 'not_found') {
            await queryClient.invalidateQueries({ queryKey: ['profile'] })
            setProblem(copyFor('not_found'))
          }
        }
        return result
      } finally {
        setBusy(false)
      }
    },
  }

  /** One track change. Returns an error sentence, or null; `not_found` refreshes both lists. */
  async function track<T>(
    action: () => Promise<Result<T>>,
    done: string,
  ): Promise<{ failure: string | null; data?: T }> {
    setProblem(null)
    setBusy(true)
    try {
      const result = await action()
      if (result.ok) {
        announce(done)
        await queryClient.invalidateQueries({ queryKey: ['tracks'] })
        return { failure: null, data: result.data }
      }
      if (result.code === 'unauthorized') {
        void navigate({ to: '/sign-in' })
        return { failure: '' }
      }
      if (result.code === 'not_found') {
        await queryClient.invalidateQueries({ queryKey: ['tracks'] })
        await queryClient.invalidateQueries({ queryKey: ['profile'] })
      }
      return { failure: trackCopy(result.code).body }
    } finally {
      setBusy(false)
    }
  }

  if (chosen) {
    ctx.emphasis = {
      track: chosen.name,
      isOn: (kind, id) => isEmphasised(chosen, kind, id),
      toggle: async (kind, id) =>
        (
          await track(
            () =>
              setEmphasis(chosen.id, kind, id, !isEmphasised(chosen, kind, id)),
            isEmphasised(chosen, kind, id)
              ? 'Removed from this track.'
              : 'Emphasised for this track.',
          )
        ).failure,
    }
  }

  async function add(kind: Kind, values: FormValues): Promise<boolean> {
    const checked = fromForm(kind, values, null)
    if (!checked.ok) return false
    const result = await ctx.run(
      () => addItem(kind, checked.body),
      'Added.',
      kind,
    )
    if (result.ok) {
      setAddError(null)
      setAdding(null)
      return true
    }
    setAddError(copyFor(result.code).body)
    return false
  }

  async function confirmEverything() {
    const result = await ctx.run(() => confirmAll(), 'Confirmed everything.')
    if (result.ok) {
      announce(
        result.data.confirmed === 1
          ? 'Confirmed 1 fact.'
          : `Confirmed ${result.data.confirmed} facts.`,
      )
      // The Confirm all button is disabled now; keep focus on the page title.
      requestAnimationFrame(() => titleRef.current?.focus())
    } else if (result.code !== 'not_found') {
      setProblem(copyFor(result.code))
    }
  }

  const topProblem = problem && (
    <Problem title={problem.title} body={problem.body} />
  )

  return (
    <div className="mx-auto flex w-full max-w-[880px] flex-col gap-6">
      <div role="status" aria-live="polite" className="sr-only">
        {notice}
      </div>

      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1
            ref={titleRef}
            tabIndex={-1}
            className="font-display text-[28px] font-bold tracking-tight text-ink"
          >
            Career profile
          </h1>
          <p className="mt-1.5 text-sm text-faint">
            Everything Jobmigo writes or scores comes from facts you have
            confirmed here.
          </p>
        </div>
        {profile && (
          <div className="flex flex-wrap gap-3">
            <Link to="/onboarding" className={BTN_GHOST}>
              Upload new CV
            </Link>
            <button
              type="button"
              className={BTN_PRIMARY}
              disabled={busy || progress(profile).unconfirmed === 0}
              onClick={() => void confirmEverything()}
            >
              Confirm all
              {progress(profile).unconfirmed > 0
                ? ` (${progress(profile).unconfirmed})`
                : ''}
            </button>
          </div>
        )}
      </header>

      {query.isPending && (
        <div
          role="status"
          aria-label="Loading your profile"
          className="flex animate-pulse flex-col gap-4"
        >
          <div className="h-20 rounded-2xl bg-surface-sunken" />
          <div className="h-56 rounded-[20px] bg-surface-sunken" />
        </div>
      )}

      {loadCode === 'not_found' && (
        <section className="flex max-w-xl flex-col gap-3.5 rounded-[20px] border border-border bg-surface p-6">
          <MigoSays>Your profile starts with your CV.</MigoSays>
          <h2 className="font-display text-[17px] font-bold text-ink">
            Upload your CV to begin
          </h2>
          <p className="text-[13px] leading-relaxed text-muted">
            Your profile is built from your CV, so nothing appears here until it
            has been read.
          </p>
          <Link to="/onboarding" className={`${BTN_PRIMARY} self-start`}>
            Upload CV
          </Link>
        </section>
      )}

      {loadCode && loadCode !== 'not_found' && !unauthorized && (
        <Problem
          title="We could not load your profile"
          body="Your profile is safe. Try again in a moment."
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

      {topProblem}

      {profile && (
        <>
          <Progress profile={profile} />
          <ProfileText
            profile={profile}
            ctx={ctx}
            editing={editingText}
            setEditing={setEditingText}
          />
          {tracksQuery.isPending ? (
            <div
              role="status"
              aria-label="Loading your tracks"
              className="h-24 animate-pulse rounded-[20px] bg-surface-sunken"
            />
          ) : (
            <TracksSection
              tracks={tracks}
              selectedId={chosen?.id ?? null}
              shown={shownIds(profile)}
              busy={busy}
              loadFailed={tracksQuery.isError}
              retrying={tracksQuery.isFetching}
              onRetry={() => void tracksQuery.refetch()}
              onSelect={setTrackId}
              onCreate={async (name) => {
                const done = await track(
                  () => createTrack(name),
                  'Track added.',
                )
                if (!done.failure && done.data) {
                  setTrackId(done.data.id)
                  requestAnimationFrame(() =>
                    document.getElementById(`track-${done.data?.id}`)?.focus(),
                  )
                }
                return done.failure
              }}
              onRename={async (id, name) =>
                (await track(() => renameTrack(id, name), 'Track renamed.'))
                  .failure
              }
              onSavePreferences={async (id, body) =>
                (
                  await track(
                    () => patchPreferences(id, body),
                    'Preferences saved.',
                  )
                ).failure
              }
              onDelete={async (id) => {
                const done = await track(
                  () => deleteTrack(id),
                  'Track deleted.',
                )
                if (!done.failure) setTrackId(null)
                return done.failure
              }}
            />
          )}
          {KINDS.map((kind) => {
            const facts = profile[LIST_KEY[kind]] as Fact[]
            return (
              <Section
                key={kind}
                kind={kind}
                title={SECTION_TITLE[kind]}
                note={NOTE[kind]}
                ctx={ctx}
                adding={adding === kind}
                setAdding={(open) => {
                  setAddError(null)
                  setAdding(open ? kind : null)
                }}
                addError={addError}
                onAdd={(values) => add(kind, values)}
                addLabel={ADD_LABEL[kind]}
              >
                {facts.length === 0 && (
                  <p className="border-t border-surface-sunken px-4 py-4 text-sm text-faint">
                    Nothing here yet.
                  </p>
                )}
                {kind === 'skill' ? (
                  <SkillChips
                    skills={facts}
                    ctx={ctx}
                    open={openSkill}
                    setOpen={setOpenSkill}
                  />
                ) : (
                  facts.map((fact) => (
                    <FactRow key={fact.id} kind={kind} fact={fact} ctx={ctx} />
                  ))
                )}
              </Section>
            )
          })}
        </>
      )}
    </div>
  )
}

/** The ids of every fact on screen. */
function shownIds(profile: Profile): Set<string> {
  const ids = new Set<string>()
  for (const kind of KINDS) {
    for (const fact of profile[LIST_KEY[kind]] as Fact[]) ids.add(fact.id)
  }
  return ids
}

function Progress({ profile }: { profile: Profile }) {
  const state = progress(profile)
  const steps = [
    { n: '1', label: 'Upload CV', state: 'Done', done: true },
    { n: '2', label: 'Review profile', state: state.text, done: false },
    { n: '3', label: 'Make it yours', state: 'Not started', done: false },
    { n: '4', label: 'First evaluation', state: 'Not started', done: false },
  ]
  return (
    <ol
      aria-label="Setup progress"
      className="m-0 flex list-none flex-wrap gap-3 p-0"
    >
      {steps.map((step) => (
        <li
          key={step.n}
          aria-current={step.n === '2' ? 'step' : undefined}
          className={`flex flex-[1_1_180px] items-center gap-3 rounded-2xl border bg-surface px-4 py-3.5 ${
            step.n === '2' ? 'border-accent-mid' : 'border-border'
          }`}
        >
          <span
            className={`flex size-7 shrink-0 items-center justify-center rounded-full text-[13px] font-extrabold ${
              step.done
                ? 'bg-good-bg text-good-ink'
                : step.n === '2'
                  ? 'bg-accent-strong text-white'
                  : 'bg-border text-muted'
            }`}
          >
            {step.n}
          </span>
          <span className="text-sm font-bold text-ink">
            {step.label}
            <span className="mt-px block text-xs font-semibold text-faint">
              {step.state}
            </span>
          </span>
        </li>
      ))}
    </ol>
  )
}

function ProfileText({
  profile,
  ctx,
  editing,
  setEditing,
}: {
  profile: Profile
  ctx: Ctx
  editing: boolean
  setEditing: (open: boolean) => void
}) {
  const [headline, setHeadline] = useState(profile.headline ?? '')
  const [summary, setSummary] = useState(profile.summary ?? '')
  const [error, setError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<{
    headline?: string
    summary?: string
  }>({})
  const edit = useRef<HTMLButtonElement>(null)
  const headlineInput = useRef<HTMLInputElement>(null)
  const was = useRef(false)
  useEffect(() => {
    if (editing) was.current = true
    else if (was.current) {
      was.current = false
      edit.current?.focus()
    }
  }, [editing])

  useEffect(() => {
    if (editing) headlineInput.current?.focus()
  }, [editing])

  if (!editing) {
    return (
      <section
        aria-label="Headline and summary"
        className="flex flex-wrap items-start justify-between gap-3 rounded-[20px] border border-border bg-surface p-5"
      >
        <div className="min-w-0">
          <p className="break-words text-base font-bold text-ink">
            {profile.headline ?? 'No headline yet'}
          </p>
          {profile.summary && (
            <p className="mt-1.5 break-words text-sm leading-relaxed text-body">
              {profile.summary}
            </p>
          )}
        </div>
        <button
          ref={edit}
          type="button"
          className={BTN}
          disabled={ctx.busy}
          onClick={() => {
            setHeadline(profile.headline ?? '')
            setSummary(profile.summary ?? '')
            setError(null)
            setEditing(true)
          }}
        >
          Edit headline
        </button>
      </section>
    )
  }
  return (
    <form
      noValidate
      aria-label="Edit headline and summary"
      onSubmit={async (event) => {
        event.preventDefault()
        const tidy = (text: string) => text.replace(/\s+/g, ' ').trim()
        const problems: { headline?: string; summary?: string } = {}
        if (tidy(headline).length > 200) {
          problems.headline = 'The headline can be 200 characters or fewer.'
        }
        if (tidy(summary).length > 2000) {
          problems.summary = 'The summary can be 2,000 characters or fewer.'
        }
        setFieldError(problems)
        if (problems.headline || problems.summary) return
        const body: Record<string, string | null> = {}
        if (headline.trim() !== (profile.headline ?? '')) {
          body.headline = headline.trim() || null
        }
        if (summary.trim() !== (profile.summary ?? '')) {
          body.summary = summary.trim() || null
        }
        if (Object.keys(body).length === 0) {
          setEditing(false)
          return
        }
        const result = await ctx.run(() => patchProfile(body), 'Saved.')
        if (result.ok) setEditing(false)
        else setError(copyFor(result.code).body)
      }}
      className="flex flex-col gap-3.5 rounded-[20px] border border-border bg-surface p-5"
    >
      <label className="flex flex-col gap-1.5 text-[13px] font-bold text-muted">
        Headline
        <input
          ref={headlineInput}
          type="text"
          value={headline}
          aria-invalid={fieldError.headline ? true : undefined}
          aria-describedby={fieldError.headline ? 'headline-err' : undefined}
          onChange={(event) => setHeadline(event.target.value)}
          className="min-h-11 w-full rounded-xl border border-border-strong bg-surface px-3 text-sm font-normal text-ink"
        />
      </label>
      <label className="flex flex-col gap-1.5 text-[13px] font-bold text-muted">
        Summary
        <textarea
          rows={4}
          value={summary}
          aria-invalid={fieldError.summary ? true : undefined}
          aria-describedby={fieldError.summary ? 'summary-err' : undefined}
          onChange={(event) => setSummary(event.target.value)}
          className="w-full rounded-xl border border-border-strong bg-surface px-3 py-2.5 text-sm font-normal text-ink"
        />
      </label>
      {fieldError.headline && (
        <p id="headline-err" className="text-xs font-bold text-bad-ink">
          {fieldError.headline}
        </p>
      )}
      {fieldError.summary && (
        <p id="summary-err" className="text-xs font-bold text-bad-ink">
          {fieldError.summary}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm font-bold text-bad-ink">
          {error}
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
          onClick={() => setEditing(false)}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

function SkillChips({
  skills,
  ctx,
  open,
  setOpen,
}: {
  skills: Fact[]
  ctx: Ctx
  open: string | null
  setOpen: (id: string | null) => void
}) {
  const selected = skills.find((skill) => skill.id === open) ?? null
  return (
    <div className="border-t border-surface-sunken px-4 py-4">
      <div className="flex flex-wrap gap-2.5">
        {skills.map((skill) => {
          const name = (skill as { name: string }).name
          const unconfirmed = skill.status === 'extracted'
          return (
            <button
              key={skill.id}
              type="button"
              id={`chip-${skill.id}`}
              aria-expanded={open === skill.id}
              aria-controls={open === skill.id ? 'skill-panel' : undefined}
              aria-label={`${name}, ${STATUS_LABEL[skill.status].toLowerCase()}`}
              onClick={() => {
                const next = open === skill.id ? null : skill.id
                setOpen(next)
                if (next) {
                  requestAnimationFrame(() =>
                    document.getElementById('skill-panel')?.focus(),
                  )
                }
              }}
              className={`inline-flex min-h-11 items-center rounded-full border-[1.5px] bg-surface px-3.5 text-[13px] font-bold text-ink hover:bg-surface-muted ${
                unconfirmed
                  ? 'border-dashed border-accent-mid'
                  : 'border-solid border-accent-mid bg-accent-soft'
              }`}
            >
              {name}
            </button>
          )
        })}
      </div>
      {selected && (
        <div
          id="skill-panel"
          tabIndex={-1}
          role="group"
          aria-label={`Skill: ${(selected as { name: string }).name}`}
          className="mt-3 rounded-2xl border border-border bg-bg"
        >
          <FactRow
            key={selected.id}
            kind="skill"
            fact={selected}
            ctx={ctx}
            onClose={() => {
              setOpen(null)
              requestAnimationFrame(() =>
                document.getElementById(`chip-${selected.id}`)?.focus(),
              )
            }}
          />
        </div>
      )}
    </div>
  )
}
