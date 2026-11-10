import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/profile/items/$kind/$id/confirm')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const { handleItemConfirm } = await import('#/server/profile/http')
        return handleItemConfirm(request, params.kind, params.id)
      },
    },
  },
})
