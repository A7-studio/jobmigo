import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/tracks/$id/preferences')({
  server: {
    handlers: {
      PATCH: async ({ request, params }) => {
        const { handlePreferences } = await import('#/server/tracks/http')
        return handlePreferences(request, params.id)
      },
    },
  },
})
