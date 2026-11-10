/** Pure rules for the track chips on the profile screen: shapes, name check and copy. */
import type { Kind } from './profile-view'

export const MAX_TRACKS = 10
export const MAX_NAME_CHARS = 60

export type WorkMode = 'remote' | 'hybrid' | 'onsite'
export type Weight = 'must' | 'important' | 'nice'
export const WORK_MODES: { value: WorkMode; label: string }[] = [
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'onsite', label: 'On-site' },
]

export type Preferences = {
  targetRoles: string[]
  salaryFloor: number | null
  currency: string | null
  workModes: WorkMode[]
  locations: string[]
  eligibility: string | null
  criteria: { label: string; weight: Weight }[]
  dealbreakers: string[]
  doNotApply: string[]
}

export type Track = {
  id: string
  name: string
  variantVersion: number
  emphasis: { kind: Kind; itemId: string }[]
  preferences: Preferences
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

/** What a person types in the preferences panel; lists are one item per line. */
export type PrefsForm = {
  targetRoles: string
  salaryFloor: string
  currency: string
  workModes: WorkMode[]
  locations: string
  eligibility: string
  must: string
  important: string
  nice: string
  dealbreakers: string
  doNotApply: string
}

export type PrefsField = keyof PrefsForm

/** Limits the engine enforces; the form checks them first so errors appear beside the field. */
export const LIMITS = {
  roles: { items: 10, chars: 80 },
  locations: { items: 10, chars: 80 },
  dealbreakers: { items: 10, chars: 120 },
  doNotApply: { items: 50, chars: 80 },
  criteria: { items: 30, chars: 120 },
  eligibility: 500,
  salary: 10_000_000,
} as const

const lines = (items: string[]) => items.join('\n')

export function toPrefsForm(p: Preferences): PrefsForm {
  const group = (weight: Weight) =>
    lines(p.criteria.filter((c) => c.weight === weight).map((c) => c.label))
  return {
    targetRoles: lines(p.targetRoles),
    salaryFloor: p.salaryFloor === null ? '' : String(p.salaryFloor),
    currency: p.currency ?? '',
    workModes: [...p.workModes],
    locations: lines(p.locations),
    eligibility: p.eligibility ?? '',
    must: group('must'),
    important: group('important'),
    nice: group('nice'),
    dealbreakers: lines(p.dealbreakers),
    doNotApply: lines(p.doNotApply),
  }
}

const splitLines = (text: string) =>
  text
    .split('\n')
    .map(tidyName)
    .filter((line) => line !== '')

function listError(
  items: string[],
  limit: { items: number; chars: number },
  noun: string,
): string | null {
  if (items.length > limit.items) {
    return `Use ${limit.items} ${noun} or fewer (now ${items.length}).`
  }
  const long = items.find((item) => item.length > limit.chars)
  if (long !== undefined) {
    return `Each line can be ${limit.chars} characters or fewer.`
  }
  const seen = new Set<string>()
  for (const item of items) {
    const key = item.toLowerCase()
    if (seen.has(key)) return 'Each line should be different.'
    seen.add(key)
  }
  return null
}

export type PrefsResult =
  | { ok: true; body: Record<string, unknown> }
  | { ok: false; errors: Partial<Record<PrefsField, string>> }

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

/**
 * Check the form and turn it into a request body holding only what changed, the way the
 * engine will read it. An error is returned per field.
 */
export function fromPrefsForm(
  form: PrefsForm,
  original: Preferences,
): PrefsResult {
  const errors: Partial<Record<PrefsField, string>> = {}
  const roles = splitLines(form.targetRoles)
  const locations = splitLines(form.locations)
  const dealbreakers = splitLines(form.dealbreakers)
  const doNotApply = splitLines(form.doNotApply)
  const criteria = (['must', 'important', 'nice'] as const).flatMap((weight) =>
    splitLines(form[weight]).map((label) => ({ label, weight })),
  )

  const checks: [PrefsField, string | null][] = [
    ['targetRoles', listError(roles, LIMITS.roles, 'roles')],
    ['locations', listError(locations, LIMITS.locations, 'places')],
    [
      'dealbreakers',
      listError(dealbreakers, LIMITS.dealbreakers, 'firm no rules'),
    ],
    ['doNotApply', listError(doNotApply, LIMITS.doNotApply, 'companies')],
  ]
  for (const [field, message] of checks) if (message) errors[field] = message

  const criteriaProblem = listError(
    criteria.map((c) => c.label),
    LIMITS.criteria,
    'criteria in all',
  )
  if (criteriaProblem) {
    const field = (['must', 'important', 'nice'] as const).find((w) =>
      splitLines(form[w]).some((l) => l.length > LIMITS.criteria.chars),
    )
    errors[field ?? 'must'] = criteriaProblem
  }

  const eligibility = tidyName(form.eligibility)
  if (eligibility.length > LIMITS.eligibility) {
    errors.eligibility = `Use ${LIMITS.eligibility} characters or fewer (now ${eligibility.length}).`
  }

  const rawSalary = form.salaryFloor.replace(/[\s,]/g, '')
  let salary: number | null = null
  if (rawSalary !== '') {
    if (!/^\d+$/.test(rawSalary) || Number(rawSalary) > LIMITS.salary) {
      errors.salaryFloor = `Enter a whole number up to ${LIMITS.salary.toLocaleString('en-US')}.`
    } else salary = Number(rawSalary)
  }
  const currency = form.currency.trim().toUpperCase()
  if (currency !== '' && !/^[A-Z]{3}$/.test(currency)) {
    errors.currency = 'Use a three-letter code such as USD or KES.'
  } else if (salary !== null && currency === '') {
    errors.currency = 'Add the currency for that salary.'
  }

  if (Object.keys(errors).length > 0) return { ok: false, errors }

  const next: Preferences = {
    targetRoles: roles,
    salaryFloor: salary,
    currency: currency === '' ? null : currency,
    workModes: WORK_MODES.map((m) => m.value).filter((m) =>
      form.workModes.includes(m),
    ),
    locations,
    eligibility: eligibility === '' ? null : eligibility,
    criteria,
    dealbreakers,
    doNotApply,
  }
  const body: Record<string, unknown> = {}
  for (const key of Object.keys(next) as (keyof Preferences)[]) {
    if (!same(next[key], original[key])) body[key] = next[key]
  }
  return { ok: true, body }
}
