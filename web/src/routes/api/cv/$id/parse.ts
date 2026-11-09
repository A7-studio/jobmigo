import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/cv/$id/parse')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const { handleParse } = await import('#/server/cv/http')
        return handleParse(request, params.id)
      },
    },
  },
})
