import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/cv/$id/download')({
  server: {
    handlers: {
      GET: async ({ request, params }) => {
        const { handleDownload } = await import('#/server/cv/http')
        return handleDownload(request, params.id)
      },
    },
  },
})
