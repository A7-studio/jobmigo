import { callEngine } from '../engine/client'
import type { EngineCall } from '../engine/client'
import { NotFoundError, ValidationFailedError, toResult } from '../errors'
import { requireUser } from '../identity'

/** Edits are short text; a body past this is refused before the engine sees it. */
export const MAX_BODY_BYTES = 32 * 1024
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export const KINDS = [
  'experience',
  'skill',
  'achievement',
  'project',
  'education',
] as const

export type ProfileHttpDeps = {
  requireUser?: (headers: Headers) => Promise<{ id: string }>
  fetchFn?: EngineCall['fetchFn']
  env?: EngineCall['env']
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json',
      'cache-control': 'no-store',
    },
  })
}

function failure(error: unknown): Response {
  const { status, code, message } = toResult(error)
  return json({ code, message }, status)
}

export function checkKind(kind: string) {
  if (!(KINDS as readonly string[]).includes(kind)) throw new NotFoundError()
}

export function checkId(id: string) {
  if (!UUID.test(id)) throw new NotFoundError()
}

/**
 * The JSON object sent, within the size cap; anything else is one stable 422. The cap
 * is checked from the header and again as the body streams in, so an oversized body
 * is never buffered whole.
 */
async function readBody(
  request: Request,
  maxBytes: number,
): Promise<Record<string, unknown>> {
  const declared = Number(request.headers.get('content-length'))
  if (Number.isFinite(declared) && declared > maxBytes) {
    throw new ValidationFailedError()
  }
  const chunks: Uint8Array[] = []
  let total = 0
  const reader = request.body?.getReader()
  if (reader) {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      total += value.byteLength
      if (total > maxBytes) {
        await reader.cancel()
        throw new ValidationFailedError()
      }
      chunks.push(value)
    }
  }
  const bytes = new Uint8Array(total)
  let offset = 0
  for (const chunk of chunks) {
    bytes.set(chunk, offset)
    offset += chunk.byteLength
  }
  let value: unknown
  try {
    value = JSON.parse(new TextDecoder().decode(bytes))
  } catch {
    throw new ValidationFailedError()
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new ValidationFailedError()
  }
  return value as Record<string, unknown>
}

export type Call = {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  path: string
  withBody?: boolean
  /** Body cap in bytes; the default suits short edits. */
  maxBytes?: number
  status?: number
}

export async function forward(
  request: Request,
  deps: ProfileHttpDeps,
  call: Call,
  checks: () => void = () => undefined,
): Promise<Response> {
  try {
    const user = await (deps.requireUser ?? requireUser)(request.headers)
    checks()
    const body = call.withBody
      ? await readBody(request, call.maxBytes ?? MAX_BODY_BYTES)
      : undefined
    const result = await callEngine(call.path, {
      userId: user.id,
      method: call.method,
      body,
      fetchFn: deps.fetchFn,
      env: deps.env,
    })
    if (result === undefined) return new Response(null, { status: 204 })
    return json(result, call.status ?? 200)
  } catch (error) {
    return failure(error)
  }
}

export const handleProfile = (request: Request, deps: ProfileHttpDeps = {}) =>
  forward(request, deps, { method: 'GET', path: '/internal/profile' })

export const handleProfilePatch = (
  request: Request,
  deps: ProfileHttpDeps = {},
) =>
  forward(request, deps, {
    method: 'PATCH',
    path: '/internal/profile',
    withBody: true,
  })

export const handleConfirmAll = (
  request: Request,
  deps: ProfileHttpDeps = {},
) =>
  forward(request, deps, {
    method: 'POST',
    path: '/internal/profile/confirm-all',
  })

export const handleAddItem = (
  request: Request,
  kind: string,
  deps: ProfileHttpDeps = {},
) =>
  forward(
    request,
    deps,
    {
      method: 'POST',
      path: `/internal/profile/items/${kind}`,
      withBody: true,
      status: 201,
    },
    () => checkKind(kind),
  )

export const handleItemPatch = (
  request: Request,
  kind: string,
  id: string,
  deps: ProfileHttpDeps = {},
) =>
  forward(
    request,
    deps,
    {
      method: 'PATCH',
      path: `/internal/profile/items/${kind}/${id}`,
      withBody: true,
    },
    () => {
      checkKind(kind)
      checkId(id)
    },
  )

export const handleItemConfirm = (
  request: Request,
  kind: string,
  id: string,
  deps: ProfileHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'POST', path: `/internal/profile/items/${kind}/${id}/confirm` },
    () => {
      checkKind(kind)
      checkId(id)
    },
  )

export const handleItemDelete = (
  request: Request,
  kind: string,
  id: string,
  deps: ProfileHttpDeps = {},
) =>
  forward(
    request,
    deps,
    { method: 'DELETE', path: `/internal/profile/items/${kind}/${id}` },
    () => {
      checkKind(kind)
      checkId(id)
    },
  )
