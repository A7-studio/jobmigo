import { createMiddleware, createStart } from '@tanstack/react-start'
import { runWithRequestId } from '#/server/logger'

const requestId = createMiddleware({ type: 'request' }).server(
  async ({ request, next }) => {
    const id = request.headers.get('x-request-id') ?? crypto.randomUUID()
    const result = await runWithRequestId(id, () => next())
    result.response.headers.set('x-request-id', id)
    return result
  },
)

export const startInstance = createStart(() => ({
  requestMiddleware: [requestId],
}))
