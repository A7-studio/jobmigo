import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/$id/evaluations')({
  server: {
    handlers: {
      GET: async ({ request, params }) => {
        const { handleJobEvaluations } = await import('#/server/jobs/http')
        return handleJobEvaluations(request, params.id)
      },
    },
  },
})
