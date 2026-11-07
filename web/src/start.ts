import { createMiddleware, createStart } from '@tanstack/react-start'
import { withRequestId } from '#/server/request-id'

const requestId = createMiddleware({ type: 'request' }).server(
  ({ request, next }) => withRequestId(request, () => next()),
)

export const startInstance = createStart(() => ({
  requestMiddleware: [requestId],
}))
