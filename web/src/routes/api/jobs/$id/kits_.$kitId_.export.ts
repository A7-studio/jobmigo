import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/jobs/$id/kits_/$kitId_/export')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const { handleJobKitExport } = await import('#/server/jobs/http')
        return handleJobKitExport(request, params.id, params.kitId)
      },
    },
  },
})
