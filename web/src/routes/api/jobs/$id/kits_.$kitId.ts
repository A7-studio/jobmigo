import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/$id/kits_/$kitId')({
  server: {
    handlers: {
      PATCH: async ({ request, params }) => {
        const { handleJobKitEdit } = await import('#/server/jobs/http')
        return handleJobKitEdit(request, params.id, params.kitId)
      },
    },
  },
})
