import type { CvRow } from './cv-view'

export type Result<T> =
  { ok: true; data: T } | { ok: false; code: string; message: string }

type Deps = { fetchFn?: typeof fetch }

export type Draft = {
  id: string
  cvId: string
  headline: string | null
  summary: string | null
  experiences: {
    id: string
    company: string
    role: string
    start: string | null
    end: string | null
    isCurrent: boolean
  }[]
  skills: unknown[]
  achievements: unknown[]
  projects: unknown[]
  education: unknown[]
}

const SAFE_CODE = /^[a-z][a-z_]{0,49}$/

/**
 * One call to our own API. An HTTP error becomes `{ ok: false, code }` with the
 * stable code from the server (or `unexpected`/`network`); it never throws.
 */
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

export const uploadCv = (file: File, deps: Deps = {}) =>
  call<CvRow>(
    '/api/cv',
    {
      method: 'POST',
      body: file,
      // The browser sends the name percent-encoded so it is header-safe.
      headers: { 'x-filename': encodeURIComponent(file.name) },
    },
    deps,
  )

export const listCvs = (deps: Deps = {}) =>
  call<{ items: CvRow[] }>('/api/cv', { method: 'GET' }, deps)

export const getCv = (id: string, deps: Deps = {}) =>
  call<CvRow>(`/api/cv/${id}`, { method: 'GET' }, deps)

export const startParse = (id: string, deps: Deps = {}) =>
  call<CvRow>(`/api/cv/${id}/parse`, { method: 'POST' }, deps)

export const getDraft = (id: string, deps: Deps = {}) =>
  call<Draft>(`/api/cv/${id}/profile`, { method: 'GET' }, deps)

export const deleteCv = (id: string, deps: Deps = {}) =>
  call<undefined>(`/api/cv/${id}`, { method: 'DELETE' }, deps)
