import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/$id/kit')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const { handleJobKit } = await import('#/server/jobs/http')
        return handleJobKit(request, params.id)
      },
    },
  },
})
