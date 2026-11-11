import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/$id/screens')({
  server: {
    handlers: {
      GET: async ({ request, params }) => {
        const { handleJobScreens } = await import('#/server/jobs/http')
        return handleJobScreens(request, params.id)
      },
    },
  },
})
