/** Pure rules for the track chips on the profile screen: shapes, name check and copy. */
import type { Kind } from './profile-view'

export const MAX_TRACKS = 10
export const MAX_NAME_CHARS = 60

export type Track = {
  id: string
  name: string
  variantVersion: number
  emphasis: { kind: Kind; itemId: string }[]
}

/** Whitespace collapses the way the engine does it, so lengths agree. */
export const tidyName = (value: string) => value.replace(/\s+/g, ' ').trim()

export type NameResult =
  { ok: true; name: string } | { ok: false; error: string }

/** Check a typed name against the rules the engine enforces, or say what is wrong. */
export function checkName(value: string, others: string[]): NameResult {
  const name = tidyName(value)
  if (name === '') return { ok: false, error: 'Give the track a name.' }
  if (name.length > MAX_NAME_CHARS) {
    return {
      ok: false,
      error: `Use ${MAX_NAME_CHARS} characters or fewer (now ${name.length}).`,
    }
  }
  const same = name.toLowerCase()
  if (others.some((other) => other.toLowerCase() === same)) {
    return { ok: false, error: 'You already have a track with that name.' }
  }
  return { ok: true, name }
}

export const isEmphasised = (track: Track, kind: Kind, id: string) =>
  track.emphasis.some((e) => e.kind === kind && e.itemId === id)

/** How many emphasised facts still exist among the ones the screen shows. */
export const emphasisCount = (track: Track, shown: Set<string>) =>
  track.emphasis.filter((e) => shown.has(e.itemId)).length

type Copy = { title: string; body: string }

/** Calm wording for an error code; never shows a code or a raw server message. */
export function trackCopy(code: string): Copy {
  switch (code) {
    case 'validation_failed':
      return {
        title: 'That name was not accepted',
        body: 'Check it and try again. Your tracks are unchanged.',
      }
    case 'already_exists':
      return {
        title: 'You already have that track',
        body: 'Pick a different name.',
      }
    case 'limit_reached':
      return {
        title: 'That is the most tracks you can keep',
        body: `You can keep up to ${MAX_TRACKS}. Delete one you no longer need first.`,
      }
    case 'not_confirmed':
      return {
        title: 'Confirm that fact first',
        body: 'Only facts you have confirmed can be emphasised for a track.',
      }
    case 'not_found':
      return {
        title: 'That is no longer there',
        body: 'It may have been removed in another tab. We refreshed the list.',
      }
    case 'network':
      return {
        title: 'We could not reach Jobmigo',
        body: 'Check your connection and try again. Nothing changed.',
      }
    default:
      return {
        title: 'Something went wrong',
        body: 'Try again in a moment. Your tracks are unchanged.',
      }
  }
}
