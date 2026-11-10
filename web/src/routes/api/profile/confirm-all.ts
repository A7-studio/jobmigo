import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/profile/confirm-all')({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const { handleConfirmAll } = await import('#/server/profile/http')
        return handleConfirmAll(request)
      },
    },
  },
})
