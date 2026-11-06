import { createServerFn } from '@tanstack/react-start'
import { getRequestHeaders } from '@tanstack/react-start/server'

export const getSession = createServerFn({ method: 'GET' }).handler(
  async () => {
    const { auth } = await import('./auth')
    const session = await auth.api.getSession({ headers: getRequestHeaders() })
    return session ? { user: session.user } : null
  },
)

export const getAuthConfig = createServerFn({ method: 'GET' }).handler(
  async () => {
    const { googleEnabled } = await import('./auth')
    return { google: googleEnabled }
  },
)

export const getMe = createServerFn({ method: 'GET' }).handler(async () => {
  const { auth } = await import('./auth')
  const { buildMe } = await import('#/server/me')
  return buildMe(await auth.api.getSession({ headers: getRequestHeaders() }))
})
