import { afterEach, describe, expect, it, vi } from 'vitest'
import { PermissionDeniedError, UnauthorizedError } from '#/server/errors'
import { handleAiUsage } from '#/server/admin/http'

const getSession = vi.fn()
vi.mock('#/lib/auth', () => ({ auth: { api: { getSession } } }))

const USER = '3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44'
const TOKEN = 'a-very-secret-engine-token-of-sufficient-length'
const env = { ENGINE_URL: 'http://engine.test:8000', ENGINE_TOKEN: TOKEN }
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })
const get = (query = '') =>
  new Request(`http://app.test/api/admin/ai-usage${query}`, { method: 'GET' })

afterEach(() => {
  vi.restoreAllMocks()
  getSession.mockReset()
})

describe('the AI usage handler', () => {
  it('refuses a signed-out caller with 401 and never calls the engine', async () => {
    getSession.mockResolvedValue(null)
    const fetchFn = vi.fn()
    const response = await handleAiUsage(get(), { fetchFn, env })
    expect(response.status).toBe(401)
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('refuses someone who is not staff with 403 and never calls the engine', async () => {
    const fetchFn = vi.fn()
    const response = await handleAiUsage(get(), {
      fetchFn,
      env,
      requireStaff: async () => {
        throw new PermissionDeniedError()
      },
    })
    expect(response.status).toBe(403)
    expect(await response.json()).toMatchObject({ code: 'forbidden' })
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('refuses an unauthorised caller the same way as every other route', async () => {
    const response = await handleAiUsage(get(), {
      fetchFn: vi.fn(),
      env,
      requireStaff: async () => {
        throw new UnauthorizedError()
      },
    })
    expect(response.status).toBe(401)
  })

  it('passes the window to the engine and returns its answer', async () => {
    const fetchFn = vi.fn(async () => reply({ days: 7, workflows: [] }))
    const response = await handleAiUsage(get('?days=7'), {
      fetchFn,
      env,
      requireStaff: async () => ({ id: USER }),
    })
    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({ days: 7, workflows: [] })
    const [url, init] = fetchFn.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ]
    expect(url).toBe('http://engine.test:8000/internal/admin/ai-usage?days=7')
    expect(init.method).toBe('GET')
  })

  it('defaults to thirty days and refuses a bad window before the engine', async () => {
    const ok = vi.fn(async () => reply({ days: 30 }))
    await handleAiUsage(get(), {
      fetchFn: ok,
      env,
      requireStaff: async () => ({ id: USER }),
    })
    expect((ok.mock.calls[0] as unknown as [string])[0]).toContain('days=30')
    for (const bad of ['?days=0', '?days=366', '?days=abc', '?days=1.5']) {
      const fetchFn = vi.fn()
      const response = await handleAiUsage(get(bad), {
        fetchFn,
        env,
        requireStaff: async () => ({ id: USER }),
      })
      expect(response.status).toBe(422)
      expect(fetchFn).not.toHaveBeenCalled()
    }
  })
})
