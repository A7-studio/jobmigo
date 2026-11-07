import { createFileRoute } from '@tanstack/react-router'
import { readinessResponse } from '#/server/health'

export const Route = createFileRoute('/readyz')({
  server: { handlers: { GET: () => readinessResponse() } },
})
