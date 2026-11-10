import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/')({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const { handleJobs } = await import('#/server/jobs/http')
        return handleJobs(request)
      },
      POST: async ({ request }) => {
        const { handleJobCreate } = await import('#/server/jobs/http')
        return handleJobCreate(request)
      },
    },
  },
})
