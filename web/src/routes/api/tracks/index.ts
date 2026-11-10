import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/tracks/')({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const { handleTracks } = await import('#/server/tracks/http')
        return handleTracks(request)
      },
      POST: async ({ request }) => {
        const { handleTrackCreate } = await import('#/server/tracks/http')
        return handleTrackCreate(request)
      },
    },
  },
})
