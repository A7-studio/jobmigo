import type { OpportunityKind } from './opportunity'
import type { Result } from './profile-api'

type Deps = { fetchFn?: typeof fetch }

export type JobStatus = 'saved' | 'dismissed'
/** Where a job stands in your search. */
export type Stage =
  'saved' | 'preparing' | 'applied' | 'interviewing' | 'offer' | 'closed'
export type Outcome = 'no_response' | 'rejected' | 'interview' | 'offer'
export type Findings = {
  instructionLike: number
  invisibleInWords: number
  tagCharacters: number
  invisibleText: number
  mixedScriptWords: number
  hiddenBlocks: number
  hiddenUrls: number
}
export type Job = {
  id: string
  company: string
  title: string
  location: string | null
  sourceUrl: string | null
  status: JobStatus
  kind: OpportunityKind
  stage: Stage
  outcome: Outcome | null
  appliedAt: string | null
  /** A calendar day, YYYY-MM-DD. */
  followUpOn: string | null
  notes: string
  stageChangedAt: string
  flag: 'ok' | 'review'
  findings: Findings
  createdAt: string
}
export type JobFull = Job & { description: string }

const SAFE_CODE = /^[a-z][a-z_]{0,49}$/

/** One call to our own API. An HTTP error becomes `{ ok: false, code }`; it never throws. */
async function call<T>(
  path: string,
  init: RequestInit,
  deps: Deps,
): Promise<Result<T>> {
  const fetchFn = deps.fetchFn ?? fetch
  let response: Response
  try {
    response = await fetchFn(path, { credentials: 'same-origin', ...init })
  } catch {
    return { ok: false, code: 'network', message: 'Network error.' }
  }
  if (response.status === 204) return { ok: true, data: undefined as T }
  let body: unknown
  try {
    body = await response.json()
  } catch {
    return { ok: false, code: 'unexpected', message: 'Unexpected response.' }
  }
  if (response.ok) return { ok: true, data: body as T }
  const raw = (body as { code?: unknown } | null)?.code
  const code =
    typeof raw === 'string' && SAFE_CODE.test(raw) ? raw : 'unexpected'
  return { ok: false, code, message: 'Request failed.' }
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
})

export type NewJob = {
  company: string
  title: string
  text: string
  location?: string
  url?: string
  kind?: OpportunityKind
}

export const listJobs = (status?: JobStatus, deps: Deps = {}) =>
  call<Job[]>(
    status ? `/api/jobs?status=${status}` : '/api/jobs',
    { method: 'GET' },
    deps,
  )

export const addJob = (body: NewJob, deps: Deps = {}) =>
  call<JobFull>('/api/jobs', json('POST', body), deps)

export const getJob = (id: string, deps: Deps = {}) =>
  call<JobFull>(`/api/jobs/${id}`, { method: 'GET' }, deps)

export const setJobStatus = (id: string, status: JobStatus, deps: Deps = {}) =>
  call<JobFull>(`/api/jobs/${id}`, json('PATCH', { status }), deps)

/** What can be changed about how a job is going. `null` clears an outcome, date or note. */
export type TrackingChange = {
  stage?: Stage
  outcome?: Outcome | null
  followUpOn?: string | null
  notes?: string | null
}

/** Save where a job stands: its stage, outcome, follow-up day or notes. */
export const trackJob = (id: string, change: TrackingChange, deps: Deps = {}) =>
  call<JobFull>(`/api/jobs/${id}`, json('PATCH', change), deps)

/** Change a saved job's type. Results kept for tracks of another type stay stored, hidden. */
export const setJobKind = (
  id: string,
  kind: OpportunityKind,
  deps: Deps = {},
) => call<JobFull>(`/api/jobs/${id}`, json('PATCH', { kind }), deps)

export const deleteJob = (id: string, deps: Deps = {}) =>
  call<undefined>(`/api/jobs/${id}`, { method: 'DELETE' }, deps)

/**
 * `removed` is only ever set by a rule checked in code. `flagged` is a possible match for
 * a dealbreaker of yours found by the screen: it removes nothing, and you decide.
 */
export type ScreenOutcome = 'passed' | 'flagged' | 'removed' | 'unscreened'

/** What the rules and the cheap screen decided about one job for one track. */
export type JobScreen = {
  id: string
  jobId: string
  trackId: string
  trackName: string
  variantVersion: number
  /** The track changed after this result was made. */
  stale: boolean
  outcome: ScreenOutcome
  removedBy: 'gate' | null
  reasonCode: string | null
  /** One plain sentence. It may hold your dealbreaker and a quote from the posting: show it as text. A `flagged` result says "Possible match ...". */
  reason: string | null
  screen: { roleMatch: 'yes' | 'partial' | 'no'; note: string } | null
  updatedAt: string
}

/** Screen a saved job against every track; the results come back and are kept. */
export const screenJob = (id: string, deps: Deps = {}) =>
  call<JobScreen[]>(`/api/jobs/${id}/screen`, { method: 'POST' }, deps)

/** The kept results for a job, without running anything. */
export const getJobScreens = (id: string, deps: Deps = {}) =>
  call<JobScreen[]>(`/api/jobs/${id}/screens`, { method: 'GET' }, deps)

/** `poor` is shown as "Weak fit". There is no score and no percentage. */
export type FitBand = 'strong' | 'good' | 'stretch' | 'poor'
export type RequirementStatus = 'met' | 'partial' | 'gap' | 'unknown'
/** Our guess from the posting, never above `important`: the posting is not read for "must". */
export type Importance = 'important' | 'nice'

/** A confirmed or edited fact of your profile that a requirement points to. */
export type EvidenceRef = { kind: string; id: string; text: string }

export type EvaluatedRequirement = {
  need: string
  importance: Importance
  /** The posting's own words. Show as text. */
  quote: string
  status: RequirementStatus
  /** Empty unless the status is `met` or `partial`. */
  evidence: EvidenceRef[]
  /** One sentence written by AI. Label it as AI output. */
  note: string
}

export type EvaluationChecks = {
  salary: {
    status: 'meets' | 'below' | 'unknown'
    postingMonthly: number | null
    floorMonthly: number | null
    currency: string | null
    quote: string | null
  }
  workMode: {
    status: 'matches' | 'differs' | 'unclear'
    posting: 'remote' | 'hybrid' | 'onsite' | null
  }
  region: {
    status: 'none_found' | 'compatible' | 'mismatch' | 'unclear'
    region: string | null
  }
}

/** The evidence-based evaluation of one job for one track. */
export type Evaluation = {
  id: string
  jobId: string
  trackId: string
  trackName: string
  profileVersion: number
  /** Your profile or this track's rules changed after this result was made. */
  stale: boolean
  band: FitBand
  /** One sentence made by code, for example "Evidence for 6 of 7 must-haves". */
  summary: string
  mainGap: { need: string; status: RequirementStatus; note: string } | null
  requirements: EvaluatedRequirement[]
  checks: EvaluationChecks
  updatedAt: string
}

/** Evaluate a saved job for one track; a model is called unless nothing changed. */
export const evaluateJob = (id: string, trackId: string, deps: Deps = {}) =>
  call<Evaluation>(`/api/jobs/${id}/evaluate`, json('POST', { trackId }), deps)

/** The kept evaluations for a job, without running anything. */
export const getJobEvaluations = (id: string, deps: Deps = {}) =>
  call<Evaluation[]>(`/api/jobs/${id}/evaluations`, { method: 'GET' }, deps)

export type FetchedPage = {
  text: string
  title: string | null
  finalUrl: string
  truncated: boolean
}

/** Read a public job link; the cleaned text comes back and nothing is saved. */
export const fetchJobPage = (url: string, deps: Deps = {}) =>
  call<FetchedPage>('/api/jobs/fetch', json('POST', { url }), deps)

export type KitDocType = 'cv' | 'letter' | 'proposal' | 'answers'
/** The labels the check uses; flags say what could not be traced. */
export type KitFlag =
  'no_source' | 'unsupported_number' | 'empty' | 'too_long' | 'off_entry'
export type KitSource = { label: string; kind: string; id: string }
/** A piece of wording and the confirmed facts behind it. Show `text` as text only. */
export type KitBlock = {
  text: string
  sources: KitSource[]
  flags: KitFlag[]
  /** The numbers in `text` that none of its sources state. */
  numbers: string[]
  /** You wrote or changed this text; it is checked the same way. */
  edited?: boolean
}
export type KitContent =
  | {
      docType: 'cv'
      summary: KitBlock
      entries: {
        heading: string
        kind: string
        source: KitSource
        bullets: KitBlock[]
      }[]
      skills: (KitSource & { name: string })[]
    }
  | { docType: 'letter' | 'proposal'; paragraphs: KitBlock[] }
  | {
      docType: 'answers'
      answers: (KitBlock & { index: number; question: string })[]
    }

/** One saved version of one kit document. Only code decides `factCheck`; read the text yourself. */
export type KitVersion = {
  id: string
  jobId: string
  trackId: string
  trackName: string
  docType: KitDocType
  version: number
  profileVersion: number
  /** Your profile changed after this was written. */
  stale: boolean
  content: KitContent
  factCheck: {
    blocks: number
    flagged: number
    /** Entries or skills the model named that your facts do not back, left out. */
    omitted: number
    /** Paths of the statements you edited. Missing on a kit saved before edits existed. */
    edited?: string[]
    flags: { path: string; flags: KitFlag[]; numbers: string[] }[]
  }
  createdAt: string
}

/** Write the kit for a job and a track; a model is called unless nothing changed. */
export const writeKit = (
  id: string,
  trackId: string,
  questions: string[] = [],
  deps: Deps = {},
) =>
  call<KitVersion[]>(
    `/api/jobs/${id}/kit`,
    json('POST', questions.length > 0 ? { trackId, questions } : { trackId }),
    deps,
  )

/** Kept kit versions without running anything. With a track: every version of it. */
export const getKits = (id: string, trackId?: string, deps: Deps = {}) =>
  call<KitVersion[]>(
    trackId
      ? `/api/jobs/${id}/kits?trackId=${encodeURIComponent(trackId)}`
      : `/api/jobs/${id}/kits`,
    { method: 'GET' },
    deps,
  )

export type KitEdit =
  | { path: string; action: 'remove' }
  | { path: string; action: 'edit'; text: string }

/** Edit or remove one statement of the latest version. It is saved as the next version. */
export const editKit = (
  id: string,
  kitId: string,
  change: KitEdit,
  deps: Deps = {},
) =>
  call<KitVersion>(`/api/jobs/${id}/kits/${kitId}`, json('PATCH', change), deps)

export type ExportRequest = {
  format: 'pdf' | 'docx'
  /** The name on the document, in your own words. Not checked. */
  name: string
  /** One contact line, optional. Not checked. */
  contact?: string
}

/** The file name a download is saved under, from its `content-disposition` header. */
export function fileNameFrom(disposition: string | null): string | null {
  if (!disposition) return null
  const starred = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  if (starred?.[1]) {
    try {
      return decodeURIComponent(starred[1])
    } catch {
      return null
    }
  }
  const plain = /filename="([^"]+)"/i.exec(disposition)
  return plain?.[1] ?? null
}

/**
 * Make a PDF or DOCX of one kit version. The engine checks it again first and refuses with
 * `needs_fixing` while a statement still needs you. Nothing is stored.
 */
export async function exportKit(
  id: string,
  kitId: string,
  request: ExportRequest,
  deps: Deps = {},
): Promise<Result<{ blob: Blob; filename: string; replaced: number }>> {
  const fetchFn = deps.fetchFn ?? fetch
  let response: Response
  try {
    response = await fetchFn(`/api/jobs/${id}/kits/${kitId}/export`, {
      credentials: 'same-origin',
      ...json('POST', request),
    })
  } catch {
    return { ok: false, code: 'network', message: 'Network error.' }
  }
  if (response.ok) {
    try {
      const blob = await response.blob()
      const filename =
        fileNameFrom(response.headers.get('content-disposition')) ??
        `document.${request.format}`
      const count = Number(response.headers.get('x-export-replaced'))
      const replaced = Number.isInteger(count) && count > 0 ? count : 0
      return { ok: true, data: { blob, filename, replaced } }
    } catch {
      return { ok: false, code: 'unexpected', message: 'Unexpected response.' }
    }
  }
  let body: unknown
  try {
    body = await response.json()
  } catch {
    return { ok: false, code: 'unexpected', message: 'Unexpected response.' }
  }
  const raw = (body as { code?: unknown } | null)?.code
  const code =
    typeof raw === 'string' && SAFE_CODE.test(raw) ? raw : 'unexpected'
  return { ok: false, code, message: 'Request failed.' }
}
