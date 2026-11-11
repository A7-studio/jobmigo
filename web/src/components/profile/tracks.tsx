import { useEffect, useRef, useState } from 'react'
import { BTN, BTN_GHOST, BTN_PRIMARY, Problem } from '#/components/cv/parts'
import { MAX_TRACKS, checkName, emphasisCount } from '#/lib/tracks-view'
import type { Track } from '#/lib/tracks-view'
import { OPPORTUNITY_KINDS, kindLabel } from '#/lib/opportunity'
import type { OpportunityKind } from '#/lib/opportunity'
import { PreferencesPanel, summary } from './preferences'

/** What the track chips need from the page. Each action returns an error sentence, or null. */
export type TracksProps = {
  tracks: Track[]
  selectedId: string | null
  /** Ids of the facts on screen, so a count ignores facts that no longer exist. */
  shown: Set<string>
  busy: boolean
  loadFailed: boolean
  retrying: boolean
  onRetry: () => void
  onSelect: (id: string | null) => void
  onCreate: (name: string, kind: OpportunityKind) => Promise<string | null>
  onRename: (id: string, name: string) => Promise<string | null>
  onDelete: (id: string) => Promise<string | null>
  onSavePreferences: (
    id: string,
    body: Record<string, unknown>,
  ) => Promise<string | null>
}

const INPUT =
  'min-h-11 w-full max-w-sm rounded-xl border border-border-strong bg-surface px-3 text-sm font-normal text-ink'
const CHIP =
  'inline-flex min-h-11 items-center rounded-full border-[1.5px] px-4 text-[13px] font-bold text-ink hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60'

type Mode = 'idle' | 'adding' | 'renaming' | 'deleting' | 'preferences'

/** Tracks as a chip row (the Goals board look), with rename and delete for the chosen one. */
export function TracksSection(props: TracksProps) {
  const { tracks, selectedId, busy } = props
  const selected = tracks.find((t) => t.id === selectedId) ?? null
  const [mode, setMode] = useState<Mode>('idle')
  const [name, setName] = useState('')
  const [kind, setKind] = useState<OpportunityKind>('job')
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const back = useRef<string | null>(null)

  useEffect(() => {
    if (mode === 'adding' || mode === 'renaming') input.current?.focus()
  }, [mode])

  // The chosen track can vanish (deleted in another tab): never stay in a mode about it.
  useEffect(() => {
    if (!selected && mode !== 'idle' && mode !== 'adding') {
      setMode('idle')
      setError(null)
    }
  }, [selected, mode])

  /** Leave the form or question; focus goes to `focusId` (the control that opened it). */
  const close = (focusId: string | null = back.current) => {
    setMode('idle')
    setError(null)
    if (focusId) {
      requestAnimationFrame(() => document.getElementById(focusId)?.focus())
    }
  }
  const open = (next: Mode, from: string, value = '') => {
    back.current = from
    setName(value)
    setKind('job')
    setError(null)
    setMode(next)
  }

  async function submit() {
    const others = tracks
      .filter((t) =>
        mode === 'renaming' && t.id === selected?.id ? false : true,
      )
      .map((t) => t.name)
    const checked = checkName(name, others)
    if (!checked.ok) {
      setError(checked.error)
      input.current?.focus()
      return
    }
    const failure =
      mode === 'renaming' && selected
        ? await props.onRename(selected.id, checked.name)
        : await props.onCreate(checked.name, kind)
    if (failure) {
      setError(failure)
      input.current?.focus()
    } else close(mode === 'adding' ? null : back.current) // a new chip takes focus
  }

  return (
    <section
      aria-labelledby="tracks-title"
      className="flex flex-col gap-3.5 rounded-[20px] border border-border bg-surface p-5"
    >
      <div>
        <h2
          id="tracks-title"
          className="font-display text-[17px] font-bold text-ink"
        >
          Your tracks
        </h2>
        <p className="mt-1 text-[13px] leading-relaxed text-faint">
          A track is a kind of role you are aiming for. Choose one, then mark
          which confirmed facts it should lead with.
        </p>
      </div>

      {props.loadFailed ? (
        <Problem
          title="We could not load your tracks"
          body="Your profile is safe. Try again in a moment."
        >
          <button
            type="button"
            className={BTN_PRIMARY}
            disabled={props.retrying}
            onClick={props.onRetry}
          >
            {props.retrying ? 'Trying…' : 'Try again'}
          </button>
        </Problem>
      ) : (
        <>
          {tracks.length === 0 && mode !== 'adding' && (
            <p className="text-sm text-faint">
              You have no tracks yet. Add one, for example “Flutter and mobile”.
            </p>
          )}
          <div
            role="group"
            aria-label="Tracks"
            className="flex flex-wrap gap-2.5"
          >
            {tracks.map((track) => (
              <button
                key={track.id}
                type="button"
                id={`track-${track.id}`}
                aria-pressed={track.id === selectedId}
                disabled={
                  busy ||
                  mode === 'renaming' ||
                  mode === 'deleting' ||
                  mode === 'preferences'
                }
                onClick={() =>
                  props.onSelect(track.id === selectedId ? null : track.id)
                }
                className={`${CHIP} ${
                  track.id === selectedId
                    ? 'border-accent-mid bg-accent-soft'
                    : 'border-border-strong bg-surface'
                }`}
              >
                {track.name}
                {track.kind !== 'job' && (
                  <span className="ml-2 text-[11px] font-normal text-muted">
                    {kindLabel(track.kind)}
                  </span>
                )}
              </button>
            ))}
            {tracks.length < MAX_TRACKS && mode !== 'adding' && (
              <button
                type="button"
                id="track-add"
                className={`${CHIP} border-border-strong bg-surface`}
                disabled={busy || mode !== 'idle'}
                onClick={() => open('adding', 'track-add')}
              >
                + Add a track
              </button>
            )}
          </div>

          {(mode === 'adding' || mode === 'renaming') && (
            <form
              noValidate
              aria-label={mode === 'adding' ? 'Add a track' : 'Rename track'}
              onSubmit={(event) => {
                event.preventDefault()
                void submit()
              }}
              className="flex flex-col gap-2.5"
            >
              <label className="flex flex-col gap-1.5 text-[13px] font-bold text-muted">
                Track name
                <input
                  ref={input}
                  type="text"
                  value={name}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? 'track-name-err' : undefined}
                  onChange={(event) => setName(event.target.value)}
                  className={INPUT}
                />
              </label>
              {mode === 'adding' && (
                <fieldset className="flex flex-col gap-1.5">
                  <legend className="text-[13px] font-bold text-muted">
                    What kind of work is this track for?
                  </legend>
                  <div className="flex flex-wrap gap-2.5">
                    {OPPORTUNITY_KINDS.map((option) => (
                      <label
                        key={option}
                        className="inline-flex min-h-11 items-center gap-2 text-sm text-ink"
                      >
                        <input
                          type="radio"
                          name="track-kind"
                          value={option}
                          checked={kind === option}
                          onChange={() => setKind(option)}
                        />
                        {kindLabel(option)}
                      </label>
                    ))}
                  </div>
                  <p className="text-xs text-faint">
                    You cannot change this later. Freelance and AI training
                    tracks start as remote; you can edit that.
                  </p>
                </fieldset>
              )}
              {error && (
                <p
                  id="track-name-err"
                  role="alert"
                  className="text-xs font-bold text-bad-ink"
                >
                  {error}
                </p>
              )}
              <div className="flex flex-wrap gap-2.5">
                <button type="submit" className={BTN_PRIMARY} disabled={busy}>
                  {busy ? 'Saving…' : mode === 'adding' ? 'Add track' : 'Save'}
                </button>
                <button
                  type="button"
                  className={BTN}
                  disabled={busy}
                  onClick={() => close()}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}

          {selected && mode !== 'adding' && mode !== 'renaming' && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-surface-sunken pt-3.5">
                <p className="text-[13px] text-body">
                  <strong className="font-extrabold text-ink">
                    {selected.name}
                  </strong>
                  {' · '}
                  {emphasisCount(selected, props.shown) === 1
                    ? '1 fact emphasised'
                    : `${emphasisCount(selected, props.shown)} facts emphasised`}
                  . Use “Emphasise” on a confirmed fact below.
                </p>
                {mode === 'deleting' ? (
                  <div
                    role="group"
                    aria-label="Delete this track?"
                    className="flex flex-wrap items-center gap-2.5"
                  >
                    <span className="text-[13px] font-bold text-bad-ink">
                      Delete “{selected.name}”? Your facts stay.
                    </span>
                    <button
                      type="button"
                      className={BTN_PRIMARY}
                      disabled={busy}
                      onClick={async () => {
                        const failure = await props.onDelete(selected.id)
                        if (failure) setError(failure)
                        else close('track-add') // the track is gone; start over from Add
                      }}
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      className={BTN}
                      disabled={busy}
                      onClick={() => close()}
                    >
                      Keep
                    </button>
                    {error && (
                      <p
                        role="alert"
                        className="w-full text-xs font-bold text-bad-ink"
                      >
                        {error}
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className={BTN_GHOST}
                      disabled={busy}
                      id="track-prefs"
                      aria-expanded={mode === 'preferences'}
                      onClick={() =>
                        mode === 'preferences'
                          ? close()
                          : open('preferences', 'track-prefs')
                      }
                    >
                      Preferences · {summary(selected)}
                    </button>
                    {mode !== 'preferences' && (
                      <>
                        <button
                          type="button"
                          className={BTN_GHOST}
                          disabled={busy}
                          id="track-rename"
                          onClick={() =>
                            open('renaming', 'track-rename', selected.name)
                          }
                        >
                          Rename
                        </button>
                        <button
                          type="button"
                          className={BTN_GHOST}
                          disabled={busy}
                          id="track-delete"
                          onClick={() => open('deleting', 'track-delete')}
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
              {mode === 'preferences' && (
                <PreferencesPanel
                  key={`${selected.id}-${selected.variantVersion}`}
                  track={selected}
                  busy={busy}
                  onClose={() => close()}
                  onSave={async (body) => {
                    const failure = await props.onSavePreferences(
                      selected.id,
                      body,
                    )
                    if (!failure) close()
                    return failure
                  }}
                />
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}
