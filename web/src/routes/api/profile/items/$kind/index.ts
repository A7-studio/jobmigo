import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/profile/items/$kind/')({
  server: {
    handlers: {
      POST: async ({ request, params }) => {
        const { handleAddItem } = await import('#/server/profile/http')
        return handleAddItem(request, params.kind)
      },
    },
  },
})
