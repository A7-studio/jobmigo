import type { Result } from './profile-api'

type Deps = { fetchFn?: typeof fetch }

export type JobStatus = 'saved' | 'dismissed'
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

export const deleteJob = (id: string, deps: Deps = {}) =>
  call<undefined>(`/api/jobs/${id}`, { method: 'DELETE' }, deps)

export type ScreenOutcome = 'passed' | 'removed' | 'unscreened'

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
  removedBy: 'gate' | 'screen' | null
  reasonCode: string | null
  /** One plain sentence. It may hold your dealbreaker and a quote from the posting: show it as text. */
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

export type FetchedPage = {
  text: string
  title: string | null
  finalUrl: string
  truncated: boolean
}

/** Read a public job link; the cleaned text comes back and nothing is saved. */
export const fetchJobPage = (url: string, deps: Deps = {}) =>
  call<FetchedPage>('/api/jobs/fetch', json('POST', { url }), deps)
