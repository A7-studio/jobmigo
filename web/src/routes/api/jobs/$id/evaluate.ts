import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/$id/evaluate')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const { handleJobEvaluate } = await import('#/server/jobs/http')
        return handleJobEvaluate(request, params.id)
      },
    },
  },
})
