import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/cv/$id/')({
  server: {
    handlers: {
      GET: async ({ request, params }) => {
        const { handleStatus } = await import('#/server/cv/http')
        return handleStatus(request, params.id)
      },
      DELETE: async ({ request, params }) => {
        const { handleDelete } = await import('#/server/cv/http')
        return handleDelete(request, params.id)
      },
    },
  },
})
