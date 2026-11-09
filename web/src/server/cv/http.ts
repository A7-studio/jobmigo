import { callEngine } from '../engine/client'
import type { EngineCall } from '../engine/client'
import { CvTooLargeError, NotFoundError, toResult } from '../errors'
import { requireUser } from '../identity'

/** An early cut-off. The engine enforces the real limit and has the final say. */
export const MAX_CV_BYTES = 5 * 1024 * 1024
const UPLOAD_TIMEOUT_MS = 60_000
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
// The browser sends encodeURIComponent(name): printable ASCII only, so it is header-safe.
const SAFE_FILENAME_HEADER = /^[\x20-\x7e]{1,1024}$/

export type CvHttpDeps = {
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

/** Pass bytes through, and fail the stream once more than `maxBytes` have gone by. */
export function limitStream(
  source: ReadableStream<Uint8Array>,
  maxBytes: number,
): { stream: ReadableStream<Uint8Array>; tripped: () => boolean } {
  let total = 0
  let tripped = false
  const stream = source.pipeThrough(
    new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        total += chunk.byteLength
        if (total > maxBytes) {
          tripped = true
          controller.error(new Error('body too large'))
          return
        }
        controller.enqueue(chunk)
      },
    }),
  )
  return { stream, tripped: () => tripped }
}

function engineOptions(user: { id: string }, deps: CvHttpDeps) {
  return { userId: user.id, fetchFn: deps.fetchFn, env: deps.env }
}

export async function handleUpload(
  request: Request,
  deps: CvHttpDeps = {},
): Promise<Response> {
  try {
    const user = await (deps.requireUser ?? requireUser)(request.headers)
    const declared = Number(request.headers.get('content-length'))
    if (Number.isFinite(declared) && declared > MAX_CV_BYTES) {
      throw new CvTooLargeError()
    }
    const limited = limitStream(
      request.body ?? new Blob([]).stream(),
      MAX_CV_BYTES,
    )
    const name = request.headers.get('x-filename')
    try {
      const created = await callEngine('/internal/cv', {
        ...engineOptions(user, deps),
        method: 'POST',
        stream: limited.stream,
        headers:
          name && SAFE_FILENAME_HEADER.test(name) ? { 'x-filename': name } : {},
        timeoutMs: UPLOAD_TIMEOUT_MS,
      })
      return json(created, 201)
    } catch (error) {
      // Cutting the stream makes the engine call fail; that is the user's file, not an outage.
      if (limited.tripped()) throw new CvTooLargeError()
      throw error
    }
  } catch (error) {
    return failure(error)
  }
}

export async function handleList(
  request: Request,
  deps: CvHttpDeps = {},
): Promise<Response> {
  try {
    const user = await (deps.requireUser ?? requireUser)(request.headers)
    const result = await callEngine('/internal/cv', engineOptions(user, deps))
    return json(result)
  } catch (error) {
    return failure(error)
  }
}

/** Forward one owner-scoped engine call for a CV id the browser supplied. */
async function forward(
  request: Request,
  id: string,
  deps: CvHttpDeps,
  suffix: string,
  method: 'GET' | 'POST',
): Promise<unknown> {
  const user = await (deps.requireUser ?? requireUser)(request.headers)
  if (!UUID.test(id)) throw new NotFoundError()
  return callEngine(`/internal/cv/${id}${suffix}`, {
    ...engineOptions(user, deps),
    method,
  })
}

export async function handleStatus(
  request: Request,
  id: string,
  deps: CvHttpDeps = {},
): Promise<Response> {
  try {
    return json(await forward(request, id, deps, '', 'GET'))
  } catch (error) {
    return failure(error)
  }
}

/** Start a parse or retry a failed one: 202 while it runs, 200 once it is done. */
export async function handleParse(
  request: Request,
  id: string,
  deps: CvHttpDeps = {},
): Promise<Response> {
  try {
    const result = await forward(request, id, deps, '/parse', 'POST')
    const parsed =
      typeof result === 'object' &&
      result !== null &&
      (result as { parseStatus?: unknown }).parseStatus === 'parsed'
    return json(result, parsed ? 200 : 202)
  } catch (error) {
    return failure(error)
  }
}

export async function handleProfile(
  request: Request,
  id: string,
  deps: CvHttpDeps = {},
): Promise<Response> {
  try {
    return json(await forward(request, id, deps, '/profile', 'GET'))
  } catch (error) {
    return failure(error)
  }
}

export async function handleDownload(
  request: Request,
  id: string,
  deps: CvHttpDeps = {},
): Promise<Response> {
  try {
    const user = await (deps.requireUser ?? requireUser)(request.headers)
    if (!UUID.test(id)) throw new NotFoundError()
    const result = await callEngine<{ url?: unknown }>(
      `/internal/cv/${id}/download`,
      engineOptions(user, deps),
    )
    const location = typeof result.url === 'string' ? safeUrl(result.url) : null
    if (!location) throw new Error('engine returned no usable download link')
    return new Response(null, {
      status: 302,
      headers: { location, 'cache-control': 'no-store' },
    })
  } catch (error) {
    return failure(error)
  }
}

function safeUrl(value: string): string | null {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:' ? value : null
  } catch {
    return null
  }
}

export async function handleDelete(
  request: Request,
  id: string,
  deps: CvHttpDeps = {},
): Promise<Response> {
  try {
    const user = await (deps.requireUser ?? requireUser)(request.headers)
    if (!UUID.test(id)) throw new NotFoundError()
    await callEngine(`/internal/cv/${id}`, {
      ...engineOptions(user, deps),
      method: 'DELETE',
    })
    return new Response(null, { status: 204 })
  } catch (error) {
    return failure(error)
  }
}
