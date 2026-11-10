/** Pure rules for the profile screen: fact shapes, forms, checks and copy. */

export type Status = 'extracted' | 'confirmed' | 'edited'
export type Kind =
  'experience' | 'skill' | 'achievement' | 'project' | 'education'

export const KINDS: Kind[] = [
  'experience',
  'skill',
  'achievement',
  'project',
  'education',
]

type Base = { id: string; status: Status }
export type Experience = Base & {
  company: string
  role: string
  start: string | null
  end: string | null
  isCurrent: boolean
  bullets: string[]
}
export type Skill = Base & { name: string }
export type Achievement = Base & { text: string; experienceId: string | null }
export type Project = Base & { name: string; description: string | null }
export type Education = Base & {
  institution: string
  qualification: string | null
  start: string | null
  end: string | null
}
export type Fact = Experience | Skill | Achievement | Project | Education

export type Profile = {
  id: string
  cvId: string
  version: number
  headline: string | null
  summary: string | null
  experiences: Experience[]
  skills: Skill[]
  achievements: Achievement[]
  projects: Project[]
  education: Education[]
}

/** Which array of the profile holds each kind. */
export const LIST_KEY = {
  experience: 'experiences',
  skill: 'skills',
  achievement: 'achievements',
  project: 'projects',
  education: 'education',
} as const satisfies Record<Kind, keyof Profile>

export const SECTION_TITLE: Record<Kind, string> = {
  experience: 'Experience',
  skill: 'Skills',
  achievement: 'Achievements',
  project: 'Projects',
  education: 'Education',
}

export const STATUS_LABEL: Record<Status, string> = {
  extracted: 'Unconfirmed',
  confirmed: 'Confirmed',
  edited: 'Edited by you',
}

// ---- limits (mirror the engine's parse limits) --------------------------------

const NAME = 200
const DATE = /^\d{4}(-(0[1-9]|1[0-2]))?$/

export type Field = {
  key: string
  label: string
  type: 'text' | 'textarea' | 'checkbox' | 'experience'
  max?: number
  required?: boolean
  date?: boolean
  hint?: string
}

export const FIELDS: Record<Kind, Field[]> = {
  experience: [
    { key: 'role', label: 'Role', type: 'text', max: NAME, required: true },
    {
      key: 'company',
      label: 'Company',
      type: 'text',
      max: NAME,
      required: true,
    },
    {
      key: 'start',
      label: 'Start',
      type: 'text',
      date: true,
      hint: 'YYYY or YYYY-MM',
    },
    {
      key: 'end',
      label: 'End',
      type: 'text',
      date: true,
      hint: 'YYYY or YYYY-MM, blank if current',
    },
    { key: 'isCurrent', label: 'I work here now', type: 'checkbox' },
    {
      key: 'bullets',
      label: 'What you did',
      type: 'textarea',
      max: 500,
      hint: 'One point per line, up to 20',
    },
  ],
  skill: [
    { key: 'name', label: 'Skill', type: 'text', max: 80, required: true },
  ],
  achievement: [
    {
      key: 'text',
      label: 'Achievement',
      type: 'textarea',
      max: 500,
      required: true,
    },
    { key: 'experienceId', label: 'Related role', type: 'experience' },
  ],
  project: [
    { key: 'name', label: 'Project', type: 'text', max: 120, required: true },
    { key: 'description', label: 'Description', type: 'textarea', max: 1000 },
  ],
  education: [
    {
      key: 'institution',
      label: 'Institution',
      type: 'text',
      max: NAME,
      required: true,
    },
    { key: 'qualification', label: 'Qualification', type: 'text', max: NAME },
    {
      key: 'start',
      label: 'Start',
      type: 'text',
      date: true,
      hint: 'YYYY or YYYY-MM',
    },
    {
      key: 'end',
      label: 'End',
      type: 'text',
      date: true,
      hint: 'YYYY or YYYY-MM',
    },
  ],
}

const MAX_BULLETS = 20

export type FormValues = Record<string, string | boolean>

/** A fact as the strings and booleans an edit form holds. */
export function toForm(kind: Kind, fact: Fact | null): FormValues {
  const values: FormValues = {}
  for (const field of FIELDS[kind]) {
    const raw = fact
      ? (fact as unknown as Record<string, unknown>)[field.key]
      : undefined
    if (field.type === 'checkbox') values[field.key] = raw === true
    else if (field.key === 'bullets') {
      values[field.key] = Array.isArray(raw) ? (raw as string[]).join('\n') : ''
    } else values[field.key] = typeof raw === 'string' ? raw : ''
  }
  return values
}

export type FormResult =
  | { ok: true; body: Record<string, unknown> }
  | { ok: false; errors: Record<string, string> }

function normal(field: Field, values: FormValues): unknown {
  const raw = values[field.key]
  if (field.type === 'checkbox') return raw === true
  const text = typeof raw === 'string' ? raw.trim() : ''
  // The engine collapses runs of whitespace, so the length is checked the same way.
  const tidy = (value: string) => value.replace(/\s+/g, ' ').trim()
  if (field.key === 'bullets') {
    return text.split('\n').map(tidy).filter(Boolean)
  }
  const spaced = tidy(text)
  if (field.required) return spaced
  return spaced === '' ? null : spaced
}

/**
 * Check a form and turn it into a request body. With `original`, only the fields
 * that changed are sent (an edit); without it, every field is (an add).
 */
export function fromForm(
  kind: Kind,
  values: FormValues,
  original: Fact | null,
): FormResult {
  const errors: Record<string, string> = {}
  const body: Record<string, unknown> = {}
  const before = original ? toForm(kind, original) : null
  for (const field of FIELDS[kind]) {
    const value = normal(field, values)
    if (field.required && value === '') {
      errors[field.key] = `${field.label} is required.`
    } else if (typeof value === 'string') {
      if (field.max && value.length > field.max) {
        errors[field.key] =
          `${field.label} must be ${field.max} characters or fewer.`
      } else if (field.date && !DATE.test(value)) {
        errors[field.key] = `${field.label} must look like 2021 or 2021-03.`
      }
    } else if (Array.isArray(value)) {
      const lines = value as string[]
      if (lines.length > MAX_BULLETS) {
        errors[field.key] = `Use at most ${MAX_BULLETS} points.`
      } else if (lines.some((line) => line.length > (field.max ?? 500))) {
        errors[field.key] =
          `Each point must be ${field.max ?? 500} characters or fewer.`
      }
    }
    const unchanged =
      before !== null &&
      JSON.stringify(normal(field, before)) === JSON.stringify(value)
    if (!unchanged) body[field.key] = value
  }
  if (Object.keys(errors).length) return { ok: false, errors }
  return { ok: true, body }
}

// ---- copy ----------------------------------------------------------------------

export type Copy = { title: string; body: string }

/** Calm, specific copy for every code. Never the raw engine message or a code. */
export function copyFor(code: string): Copy {
  switch (code) {
    case 'validation_failed':
      return {
        title: 'That was not accepted',
        body: 'Check the fields and try again. Your profile is unchanged.',
      }
    case 'already_exists':
      return {
        title: 'That skill is already there',
        body: 'Your profile already has a skill with that name.',
      }
    case 'limit_reached':
      return {
        title: 'There are too many of these',
        body: 'Delete one you do not need, then add this again.',
      }
    case 'not_found':
      return {
        title: 'That item is no longer there',
        body: 'It may have been deleted. The page has been refreshed.',
      }
    case 'unauthorized':
      return {
        title: 'Please sign in again',
        body: 'Your session ended. Sign in and your profile will still be here.',
      }
    default:
      return {
        title: 'We could not save that',
        body: 'Your profile is unchanged. Try again in a moment.',
      }
  }
}

// ---- display helpers -----------------------------------------------------------

export function datesLabel(
  start: string | null,
  end: string | null,
  current: boolean,
): string {
  const to = current ? 'now' : end
  if (start && to) return `${start} to ${to}`
  if (start) return `from ${start}`
  if (to) return `until ${to}`
  return ''
}

export function allFacts(profile: Profile): { kind: Kind; fact: Fact }[] {
  return KINDS.flatMap((kind) =>
    (profile[LIST_KEY[kind]] as Fact[]).map((fact) => ({ kind, fact })),
  )
}

export type Progress = {
  reviewed: number
  total: number
  unconfirmed: number
  text: string
}

/** Confirmed and edited facts count as reviewed. */
export function progress(profile: Profile): Progress {
  const facts = allFacts(profile)
  const reviewed = facts.filter(
    ({ fact }) => fact.status !== 'extracted',
  ).length
  const total = facts.length
  const text =
    total === 0
      ? 'Nothing to review yet'
      : reviewed === total
        ? 'All reviewed'
        : `${reviewed} of ${total} reviewed`
  return { reviewed, total, unconfirmed: total - reviewed, text }
}
