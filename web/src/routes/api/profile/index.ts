import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/profile/')({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const { handleProfile } = await import('#/server/profile/http')
        return handleProfile(request)
      },
      PATCH: async ({ request }) => {
        const { handleProfilePatch } = await import('#/server/profile/http')
        return handleProfilePatch(request)
      },
    },
  },
})
