import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/tracks/$id/items/$kind/$itemId')({
  server: {
    handlers: {
      PUT: async ({ request, params }) => {
        const { handleEmphasis } = await import('#/server/tracks/http')
        return handleEmphasis(
          request,
          params.id,
          params.kind,
          params.itemId,
          true,
        )
      },
      DELETE: async ({ request, params }) => {
        const { handleEmphasis } = await import('#/server/tracks/http')
        return handleEmphasis(
          request,
          params.id,
          params.kind,
          params.itemId,
          false,
        )
      },
    },
  },
})
