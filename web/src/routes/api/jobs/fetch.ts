import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/fetch')({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const { handleJobFetch } = await import('#/server/jobs/http')
        return handleJobFetch(request)
      },
    },
  },
})
