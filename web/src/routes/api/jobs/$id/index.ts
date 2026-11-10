import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/$id/')({
  server: {
    handlers: {
      GET: async ({ request, params }) => {
        const { handleJob } = await import('#/server/jobs/http')
        return handleJob(request, params.id)
      },
      PATCH: async ({ request, params }) => {
        const { handleJobStatus } = await import('#/server/jobs/http')
        return handleJobStatus(request, params.id)
      },
      DELETE: async ({ request, params }) => {
        const { handleJobDelete } = await import('#/server/jobs/http')
        return handleJobDelete(request, params.id)
      },
    },
  },
})
