import { runWithRequestId } from './logger'

/** Keep a supplied X-Request-Id or generate one, and echo it on the response. */
export async function withRequestId<TResult extends { response: Response }>(
  request: Request,
  next: () => Promise<TResult> | TResult,
): Promise<TResult> {
  const id = request.headers.get('x-request-id') ?? crypto.randomUUID()
  const result = await runWithRequestId(id, () => next())
  result.response.headers.set('x-request-id', id)
  return result
}
