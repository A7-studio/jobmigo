import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/profile/items/$kind/$id/')({
  server: {
    handlers: {
      PATCH: async ({ request, params }) => {
        const { handleItemPatch } = await import('#/server/profile/http')
        return handleItemPatch(request, params.kind, params.id)
      },
      DELETE: async ({ request, params }) => {
        const { handleItemDelete } = await import('#/server/profile/http')
        return handleItemDelete(request, params.kind, params.id)
      },
    },
  },
})
