/** Pure rules for the CV screen: what a file may be, and what each state says. */

export const MAX_CV_BYTES = 5 * 1024 * 1024
export const POLL_INTERVAL_MS = 2_000
export const POLL_LIMIT_MS = 3 * 60 * 1000

const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export type ParseStatus = 'extracted' | 'parsing' | 'parsed' | 'failed'

export type CvRow = {
  id: string
  filename: string
  mime: string
  sizeBytes: number
  parseStatus: ParseStatus
  parseError: string | null
  createdAt: string
}

export type DraftSummary = {
  headline: string | null
  experiences: unknown[]
  skills: unknown[]
  achievements: unknown[]
  projects: unknown[]
  education: unknown[]
}

export type FileCheck =
  | { ok: true }
  | { ok: false; code: 'cv_empty' | 'cv_too_large' | 'cv_unsupported_type' }

/** Check a chosen file before sending it. The engine has the final say. */
export function validateFile(file: {
  name: string
  size: number
  type: string
}): FileCheck {
  const name = file.name.toLowerCase()
  const byName = name.endsWith('.pdf') || name.endsWith('.docx')
  const byType =
    file.type === '' ||
    file.type === 'application/octet-stream' ||
    file.type === 'application/pdf' ||
    file.type === DOCX_MIME
  if (!byName || !byType) return { ok: false, code: 'cv_unsupported_type' }
  if (file.size === 0) return { ok: false, code: 'cv_empty' }
  if (file.size > MAX_CV_BYTES) return { ok: false, code: 'cv_too_large' }
  return { ok: true }
}

export type Copy = {
  title: string
  body: string
  /** "Try again" re-runs the parse on the same CV. */
  retry: boolean
  /** "Upload another file" is offered. */
  another: boolean
}

const UPLOAD_ANOTHER = { retry: false, another: true }
const TRY_AGAIN = { retry: true, another: true }

/**
 * Calm, specific copy for every code the screen can meet. Never the raw engine
 * message, never a code shown to the user.
 */
export function copyFor(code: string): Copy {
  switch (code) {
    case 'cv_empty':
      return {
        title: 'That file is empty',
        body: 'Choose your CV as a PDF or DOCX file.',
        ...UPLOAD_ANOTHER,
      }
    case 'cv_too_large':
      return {
        title: 'That file is too large',
        body: 'The limit is 5 MB. Save a smaller copy and choose it again.',
        ...UPLOAD_ANOTHER,
      }
    case 'cv_unsupported_type':
      return {
        title: 'We can only read PDF or DOCX files',
        body: 'Save your CV as a PDF or DOCX and choose it again.',
        ...UPLOAD_ANOTHER,
      }
    case 'cv_unreadable':
      return {
        title: 'We could not read text from this file',
        body: 'It may be a scanned image or protected. Upload a text-based PDF or a DOCX.',
        ...UPLOAD_ANOTHER,
      }
    case 'unauthorized':
      return {
        title: 'Please sign in again',
        body: 'Your session ended. Sign in and your CV will still be here.',
        ...UPLOAD_ANOTHER,
      }
    case 'not_found':
      return {
        title: 'We could not find that CV',
        body: 'It may have been deleted. Upload it again to continue.',
        ...UPLOAD_ANOTHER,
      }
    case 'ai_not_configured':
      return {
        title: 'The AI service is not set up yet',
        body: 'Your CV is safe. We cannot read it until that is done, so please check back later.',
        ...UPLOAD_ANOTHER,
      }
    case 'ai_unavailable':
    case 'engine_unavailable':
      return {
        title: 'We could not reach the AI service',
        body: 'Nothing is wrong with your CV. Try again in a moment.',
        ...TRY_AGAIN,
      }
    case 'ai_output_invalid':
      return {
        title: 'The AI gave an answer we could not use',
        body: 'Your CV is safe. Try again; a second attempt often works.',
        ...TRY_AGAIN,
      }
    case 'interrupted':
      return {
        title: 'Reading your CV was interrupted',
        body: 'It stopped part way. Try again to start over.',
        ...TRY_AGAIN,
      }
    case 'text_too_long':
      return {
        title: 'This CV has too much text to read',
        body: 'Upload a shorter version, for example your last 10 years.',
        ...UPLOAD_ANOTHER,
      }
    case 'no_profile_found':
      return {
        title: 'We could not find a profile in this file',
        body: 'It may be a scanned image or mostly blank. Upload a text-based PDF or a DOCX.',
        ...UPLOAD_ANOTHER,
      }
    default:
      return {
        title: 'Something went wrong',
        body: 'Your CV is safe. Try again, or upload it again.',
        ...TRY_AGAIN,
      }
  }
}

export type Screen =
  | { kind: 'empty' }
  | { kind: 'ready'; cv: CvRow }
  | { kind: 'parsing'; cv: CvRow }
  | { kind: 'parsed'; cv: CvRow }
  | { kind: 'failed'; cv: CvRow; copy: Copy }

/** Which screen a CV row (or none) calls for. */
export function screenFor(cv: CvRow | null): Screen {
  if (!cv) return { kind: 'empty' }
  switch (cv.parseStatus) {
    case 'extracted':
      return { kind: 'ready', cv }
    case 'parsing':
      return { kind: 'parsing', cv }
    case 'parsed':
      return { kind: 'parsed', cv }
    case 'failed':
      return { kind: 'failed', cv, copy: copyFor(cv.parseError ?? 'internal') }
  }
}

/** Polling stops once the CV is settled, or after three minutes. */
export function shouldKeepPolling(
  status: ParseStatus,
  startedAtMs: number,
  nowMs: number,
): boolean {
  return status === 'parsing' && nowMs - startedAtMs < POLL_LIMIT_MS
}

const plural = (n: number, one: string, many: string) =>
  `${n} ${n === 1 ? one : many}`

/** What was found, as short phrases for the success view. */
export function summarise(draft: DraftSummary): string[] {
  const parts = [
    [draft.experiences.length, 'role', 'roles'],
    [draft.skills.length, 'skill', 'skills'],
    [draft.achievements.length, 'achievement', 'achievements'],
    [draft.projects.length, 'project', 'projects'],
    [draft.education.length, 'education entry', 'education entries'],
  ] as const
  return parts
    .filter(([n]) => n > 0)
    .map(([n, one, many]) => plural(n, one, many))
}
