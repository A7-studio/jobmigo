import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/admin/ai-usage')({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const { handleAiUsage } = await import('#/server/admin/http')
        return handleAiUsage(request)
      },
    },
  },
})
