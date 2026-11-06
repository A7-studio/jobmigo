import { useQuery } from '@tanstack/react-query'
import { getMe } from '#/lib/auth.functions'

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: () => getMe() })
}
