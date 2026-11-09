import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/cv/')({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const { handleList } = await import('#/server/cv/http')
        return handleList(request)
      },
      POST: async ({ request }) => {
        const { handleUpload } = await import('#/server/cv/http')
        return handleUpload(request)
      },
    },
  },
})
