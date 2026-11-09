import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/cv/$id/profile')({
  server: {
    handlers: {
      GET: async ({ request, params }) => {
        const { handleProfile } = await import('#/server/cv/http')
        return handleProfile(request, params.id)
      },
    },
  },
})
