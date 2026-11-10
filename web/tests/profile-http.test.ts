import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  MAX_BODY_BYTES,
  handleAddItem,
  handleConfirmAll,
  handleItemConfirm,
  handleItemDelete,
  handleItemPatch,
  handleProfile,
  handleProfilePatch,
} from '#/server/profile/http'

const getSession = vi.fn()
vi.mock('#/lib/auth', () => ({ auth: { api: { getSession } } }))

const USER = '3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44'
const ITEM = '9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d'
const TOKEN = 'a-very-secret-engine-token-of-sufficient-length'
const env = { ENGINE_URL: 'http://engine.test:8000', ENGINE_TOKEN: TOKEN }
const signedIn = async () => ({ id: USER })
type Fetch = (url: string, init: RequestInit) => Promise<Response>
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })

const request = (method: string, body?: unknown) =>
  new Request('http://app.test/x', {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: { 'content-type': 'application/json' },
  })

afterEach(() => {
  vi.restoreAllMocks()
  getSession.mockReset()
})

describe('without a session', () => {
  it('every handler answers 401 and never calls the engine', async () => {
    getSession.mockResolvedValue(null)
    const fetchFn = vi.fn()
    const deps = { fetchFn, env }
    const results = await Promise.all([
      handleProfile(request('GET'), deps),
      handleProfilePatch(request('PATCH', {}), deps),
      handleConfirmAll(request('POST'), deps),
      handleAddItem(request('POST', {}), 'skill', deps),
      handleItemPatch(request('PATCH', {}), 'skill', ITEM, deps),
      handleItemConfirm(request('POST'), 'skill', ITEM, deps),
      handleItemDelete(request('DELETE'), 'skill', ITEM, deps),
    ])
    for (const response of results) expect(response.status).toBe(401)
    expect(fetchFn).not.toHaveBeenCalled()
  })
})

describe('ordering and the body cap (review findings)', () => {
  it('answers 401 before it looks at an invalid kind or id', async () => {
    getSession.mockResolvedValue(null)
    const fetchFn = vi.fn()
    const deps = { fetchFn, env }
    for (const response of [
      await handleAddItem(request('POST', {}), 'job', deps),
      await handleItemDelete(request('DELETE'), 'skill', '../x', deps),
    ]) {
      expect(response.status).toBe(401)
    }
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('refuses an over-limit Content-Length without calling the engine', async () => {
    const fetchFn = vi.fn()
    const response = await handleProfilePatch(
      new Request('http://app.test/x', {
        method: 'PATCH',
        body: '{}',
        headers: { 'content-length': String(MAX_BODY_BYTES + 1) },
      }),
      { requireUser: signedIn, fetchFn, env },
    )
    expect(response.status).toBe(422)
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('stops a streamed body at the cap even with no length header', async () => {
    const fetchFn = vi.fn()
    let sent = 0
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        sent += 1
        if (sent > 100) return controller.close()
        controller.enqueue(new Uint8Array(1024).fill(97))
      },
    })
    const response = await handleProfilePatch(
      new Request('http://app.test/x', {
        method: 'PATCH',
        body: stream,
        // @ts-expect-error Node needs `duplex` for a streamed request body
        duplex: 'half',
      }),
      { requireUser: signedIn, fetchFn, env },
    )
    expect(response.status).toBe(422)
    expect(fetchFn).not.toHaveBeenCalled()
    expect(sent).toBeLessThan(40) // it stopped reading near the cap
  })
})

describe('forwarding', () => {
  it('sends each call to the right engine path and method for the session user', async () => {
    const fetchFn = vi.fn<Fetch>(async () => reply({ ok: 1 }))
    const deps = { requireUser: signedIn, fetchFn, env }
    await handleProfile(request('GET'), deps)
    await handleProfilePatch(request('PATCH', { headline: 'h' }), deps)
    await handleConfirmAll(request('POST'), deps)
    await handleAddItem(request('POST', { name: 'Go' }), 'skill', deps)
    await handleItemPatch(request('PATCH', { name: 'Go' }), 'skill', ITEM, deps)
    await handleItemConfirm(request('POST'), 'skill', ITEM, deps)
    await handleItemDelete(request('DELETE'), 'skill', ITEM, deps)
    expect(fetchFn.mock.calls.map(([url, init]) => [init.method, url])).toEqual(
      [
        ['GET', 'http://engine.test:8000/internal/profile'],
        ['PATCH', 'http://engine.test:8000/internal/profile'],
        ['POST', 'http://engine.test:8000/internal/profile/confirm-all'],
        ['POST', 'http://engine.test:8000/internal/profile/items/skill'],
        [
          'PATCH',
          `http://engine.test:8000/internal/profile/items/skill/${ITEM}`,
        ],
        [
          'POST',
          `http://engine.test:8000/internal/profile/items/skill/${ITEM}/confirm`,
        ],
        [
          'DELETE',
          `http://engine.test:8000/internal/profile/items/skill/${ITEM}`,
        ],
      ],
    )
    for (const [, init] of fetchFn.mock.calls) {
      expect(init.headers).toMatchObject({ 'x-user-id': USER })
    }
    expect(fetchFn.mock.calls[1][1].body).toBe(
      JSON.stringify({ headline: 'h' }),
    )
  })

  it('answers add with 201 and delete with an empty 204', async () => {
    const created = await handleAddItem(
      request('POST', { name: 'Go' }),
      'skill',
      {
        requireUser: signedIn,
        fetchFn: async () => reply({ id: ITEM }, 201),
        env,
      },
    )
    expect(created.status).toBe(201)
    const removed = await handleItemDelete(request('DELETE'), 'skill', ITEM, {
      requireUser: signedIn,
      fetchFn: async () => new Response(null, { status: 204 }),
      env,
    })
    expect(removed.status).toBe(204)
    expect(await removed.text()).toBe('')
  })
})

describe('checks before the engine', () => {
  it('answers 404 for an unknown kind or a malformed id without calling the engine', async () => {
    const fetchFn = vi.fn()
    const deps = { requireUser: signedIn, fetchFn, env }
    for (const response of [
      await handleAddItem(request('POST', {}), 'job', deps),
      await handleItemPatch(request('PATCH', {}), 'skill', '../x', deps),
      await handleItemConfirm(request('POST'), 'nope', ITEM, deps),
      await handleItemDelete(request('DELETE'), 'skill', 'x', deps),
    ]) {
      expect(response.status).toBe(404)
    }
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('refuses a body that is not a JSON object, or is over the cap, with one 422', async () => {
    const fetchFn = vi.fn()
    const deps = { requireUser: signedIn, fetchFn, env }
    const bad = [
      new Request('http://app.test/x', { method: 'PATCH', body: 'not json' }),
      new Request('http://app.test/x', { method: 'PATCH', body: '[1]' }),
      new Request('http://app.test/x', { method: 'PATCH', body: 'null' }),
      request('PATCH', { text: 'x'.repeat(MAX_BODY_BYTES) }),
    ]
    for (const r of bad) {
      const response = await handleProfilePatch(r, deps)
      expect(response.status).toBe(422)
      const body = await response.json()
      expect(body.code).toBe('validation_failed')
      expect(JSON.stringify(body)).not.toContain('xxxx')
    }
    expect(fetchFn).not.toHaveBeenCalled()
  })
})

describe('engine errors', () => {
  it("passes the engine's stable client errors through", async () => {
    for (const [status, code] of [
      [404, 'not_found'],
      [409, 'already_exists'],
      [422, 'limit_reached'],
      [422, 'validation_failed'],
    ] as const) {
      const response = await handleAddItem(
        request('POST', { name: 'a' }),
        'skill',
        {
          requireUser: signedIn,
          fetchFn: async () => reply({ code, message: 'Fixed words.' }, status),
          env,
        },
      )
      expect(response.status).toBe(status)
      expect((await response.json()).code).toBe(code)
    }
  })

  it('reports an engine 5xx as engine_unavailable without its message', async () => {
    const response = await handleProfile(request('GET'), {
      requireUser: signedIn,
      fetchFn: async () =>
        reply({ code: 'internal_error', message: 'secret detail' }, 500),
      env,
    })
    expect(response.status).toBe(502)
    const text = JSON.stringify(await response.json())
    expect(text).toContain('engine_unavailable')
    expect(text).not.toContain('secret detail')
  })
})
