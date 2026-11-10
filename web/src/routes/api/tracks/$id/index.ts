import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/tracks/$id/')({
  server: {
    handlers: {
      PATCH: async ({ request, params }) => {
        const { handleTrackRename } = await import('#/server/tracks/http')
        return handleTrackRename(request, params.id)
      },
      DELETE: async ({ request, params }) => {
        const { handleTrackDelete } = await import('#/server/tracks/http')
        return handleTrackDelete(request, params.id)
      },
    },
  },
})
