import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/$id/screen')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const { handleJobScreen } = await import('#/server/jobs/http')
        return handleJobScreen(request, params.id)
      },
    },
  },
})
