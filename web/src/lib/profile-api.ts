import type { Fact, Kind, Profile } from './profile-view'

export type Result<T> =
  { ok: true; data: T } | { ok: false; code: string; message: string }

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

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
})

export const getProfile = (deps: Deps = {}) =>
  call<Profile>('/api/profile', { method: 'GET' }, deps)

export const patchProfile = (
  body: { headline?: string | null; summary?: string | null },
  deps: Deps = {},
) => call<Profile>('/api/profile', json('PATCH', body), deps)

export const addItem = (
  kind: Kind,
  body: Record<string, unknown>,
  deps: Deps = {},
) => call<Fact>(`/api/profile/items/${kind}`, json('POST', body), deps)

export const patchItem = (
  kind: Kind,
  id: string,
  body: Record<string, unknown>,
  deps: Deps = {},
) => call<Fact>(`/api/profile/items/${kind}/${id}`, json('PATCH', body), deps)

export const confirmItem = (kind: Kind, id: string, deps: Deps = {}) =>
  call<Fact>(
    `/api/profile/items/${kind}/${id}/confirm`,
    { method: 'POST' },
    deps,
  )

export const deleteItem = (kind: Kind, id: string, deps: Deps = {}) =>
  call<undefined>(
    `/api/profile/items/${kind}/${id}`,
    { method: 'DELETE' },
    deps,
  )

export const confirmAll = (deps: Deps = {}) =>
  call<{ confirmed: number; version: number }>(
    '/api/profile/confirm-all',
    { method: 'POST' },
    deps,
  )
