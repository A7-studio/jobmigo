import { useNavigate } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { authClient } from '#/lib/auth-client'

/** Ends the session, clears what was cached for this person, and goes to sign-in. */
export function useSignOut() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  return async () => {
    await authClient.signOut()
    queryClient.clear()
    await navigate({ to: '/sign-in' })
  }
}
