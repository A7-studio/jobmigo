import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/cv/$id/')({
  server: {
    handlers: {
      DELETE: async ({ request, params }) => {
        const { handleDelete } = await import('#/server/cv/http')
        return handleDelete(request, params.id)
      },
    },
  },
})
