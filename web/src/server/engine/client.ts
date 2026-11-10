import {
  EngineNotConfiguredError,
  EngineUnavailableError,
  DomainError,
} from '../errors'
import { currentRequestId, logger } from '../logger'

type FetchLike = (input: string, init: RequestInit) => Promise<Response>

export type EngineCall = {
  /** The verified user, from `requireUser`. Never taken from client input. */
  userId: string
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  /** A raw request body streamed as is (uploads). Mutually exclusive with `body`. */
  stream?: ReadableStream<Uint8Array>
  /** Extra headers; they never replace authorization, the user id or the request id. */
  headers?: Record<string, string>
  signal?: AbortSignal
  timeoutMs?: number
  env?: Record<string, string | undefined>
  fetchFn?: FetchLike
}

const DEFAULT_TIMEOUT_MS = 30_000
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const SAFE_CODE = /^[a-z][a-z_]{0,49}$/

function engineConfig(env: Record<string, string | undefined>) {
  const url = env.ENGINE_URL?.trim()
  if (!url) {
    throw new EngineNotConfiguredError(
      'The AI engine is not configured: set ENGINE_URL.',
    )
  }
  const token = env.ENGINE_TOKEN?.trim()
  if (!token) {
    throw new EngineNotConfiguredError(
      'The AI engine is not configured: set ENGINE_TOKEN.',
    )
  }
  let base: URL
  try {
    base = new URL(url)
  } catch {
    throw new EngineNotConfiguredError(
      'The AI engine is not configured: ENGINE_URL must be a URL.',
    )
  }
  return { base, token }
}

/** A 4xx body from the engine in the stable shape, or null if it is not. */
async function stableError(response: Response): Promise<DomainError | null> {
  try {
    const body = (await response.json()) as {
      code?: unknown
      message?: unknown
    }
    if (
      typeof body.code === 'string' &&
      SAFE_CODE.test(body.code) &&
      typeof body.message === 'string' &&
      body.message.length <= 300
    ) {
      return new DomainError(response.status, body.code, body.message)
    }
  } catch {
    // Not the stable shape: treated as unavailable below.
  }
  return null
}

/**
 * Call the Python AI engine on behalf of one verified user. Sends the shared token,
 * the user id and the request id; never logs or returns the token, and never passes
 * an engine response body through unless it has the stable `{ code, message }` shape
 * and is a client error. Nothing is retried.
 */
export async function callEngine<TResult = unknown>(
  path: string,
  call: EngineCall,
): Promise<TResult> {
  const { base, token } = engineConfig(call.env ?? process.env)
  if (!UUID.test(call.userId)) {
    throw new Error('callEngine needs the verified user id (a UUID).')
  }
  if (!path.startsWith('/internal/') || path.includes('..')) {
    throw new Error('callEngine only calls /internal/ paths.')
  }

  // Check the path as the URL parser will read it: an encoded `..` must not escape /internal/.
  const target = new URL(path, base)
  if (
    target.origin !== base.origin ||
    !target.pathname.startsWith('/internal/')
  ) {
    throw new Error('callEngine only calls /internal/ paths.')
  }

  const headers: Record<string, string> = {
    ...call.headers,
    authorization: `Bearer ${token}`,
    'x-user-id': call.userId,
  }
  const requestId = currentRequestId()
  if (requestId) headers['x-request-id'] = requestId
  if (call.body !== undefined) headers['content-type'] = 'application/json'
  if (call.stream) headers['content-type'] = 'application/octet-stream'

  const timeout = AbortSignal.timeout(call.timeoutMs ?? DEFAULT_TIMEOUT_MS)
  const signal = call.signal ? AbortSignal.any([call.signal, timeout]) : timeout
  const fetchFn = call.fetchFn ?? fetch

  let response: Response
  try {
    response = await fetchFn(target.toString(), {
      method: call.method ?? 'GET',
      headers,
      // A redirect would forward the token and user id elsewhere.
      redirect: 'error',
      body: call.stream
        ? call.stream
        : call.body === undefined
          ? undefined
          : JSON.stringify(call.body),
      // A streamed request body must be declared half-duplex.
      ...(call.stream ? { duplex: 'half' } : {}),
      signal,
    })
  } catch {
    logger.warn('engine call failed', { status: 'network' })
    throw new EngineUnavailableError()
  }

  if (response.ok) {
    if (response.status === 204) return undefined as TResult
    try {
      return (await response.json()) as TResult
    } catch {
      logger.warn('engine call failed', { status: 'bad_body' })
      throw new EngineUnavailableError()
    }
  }

  logger.warn('engine call failed', { status: response.status })
  // A 401 means our own token is wrong, which is our fault, not the user's.
  if (
    response.status >= 400 &&
    response.status < 500 &&
    response.status !== 401
  ) {
    const known = await stableError(response)
    if (known) throw known
  }
  // The body may already be read or locked; releasing it is best effort.
  void response.body?.cancel().catch(() => undefined)
  throw new EngineUnavailableError()
}
