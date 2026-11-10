import type { Result } from './profile-api'
import type { Kind } from './profile-view'
import type { Track } from './tracks-view'

type Deps = { fetchFn?: typeof fetch }

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

const named = (method: string, name: string): RequestInit => ({
  method,
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ name }),
})

export const listTracks = (deps: Deps = {}) =>
  call<Track[]>('/api/tracks', { method: 'GET' }, deps)

export const createTrack = (name: string, deps: Deps = {}) =>
  call<Track>('/api/tracks', named('POST', name), deps)

export const renameTrack = (id: string, name: string, deps: Deps = {}) =>
  call<Track>(`/api/tracks/${id}`, named('PATCH', name), deps)

export const deleteTrack = (id: string, deps: Deps = {}) =>
  call<undefined>(`/api/tracks/${id}`, { method: 'DELETE' }, deps)

export const setEmphasis = (
  id: string,
  kind: Kind,
  itemId: string,
  on: boolean,
  deps: Deps = {},
) =>
  call<Track>(
    `/api/tracks/${id}/items/${kind}/${itemId}`,
    { method: on ? 'PUT' : 'DELETE' },
    deps,
  )
