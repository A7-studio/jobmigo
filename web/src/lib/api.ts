import { authClient } from '#/lib/auth-client'
import type { components } from '#/lib/api-types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'

export type Me = components['schemas']['MeResponse']

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

// The JWT lives 15 minutes; reuse it until a minute before it expires.
let cached: { token: string; expiresAt: number } | null = null

function tokenExpiry(token: string): number {
  try {
    const payload = JSON.parse(
      atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')),
    )
    return typeof payload.exp === 'number' ? payload.exp * 1000 : 0
  } catch {
    return 0
  }
}

async function getToken(): Promise<string> {
  if (cached && cached.expiresAt - 60_000 > Date.now()) return cached.token
  const { data, error } = await authClient.token()
  if (error) {
    cached = null
    throw new ApiError(401, 'unauthorized', 'You are signed out.')
  }
  cached = { token: data.token, expiresAt: tokenExpiry(data.token) }
  return data.token
}

export function clearApiToken() {
  cached = null
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = await getToken()
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { ...init.headers, authorization: `Bearer ${token}` },
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Could not reach the server.')
  }
  if (!response.ok) {
    let code = 'error'
    let message = 'Something went wrong.'
    try {
      const body = await response.json()
      code = body.error?.code ?? code
      message = body.error?.message ?? message
    } catch {
      // Non-JSON error body: keep the generic message.
    }
    if (response.status === 401) cached = null
    throw new ApiError(response.status, code, message)
  }
  return (await response.json()) as T
}

export const fetchMe = () => apiFetch<Me>('/v1/me')
