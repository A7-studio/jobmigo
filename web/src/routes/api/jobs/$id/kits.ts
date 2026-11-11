import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/$id/kits')({
  server: {
    handlers: {
      GET: async ({ request, params }) => {
        const { handleJobKits } = await import('#/server/jobs/http')
        return handleJobKits(request, params.id)
      },
    },
  },
})
