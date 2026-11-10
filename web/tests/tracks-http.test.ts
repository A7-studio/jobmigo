import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  handleEmphasis,
  handlePreferences,
  handleTrackCreate,
  handleTrackDelete,
  handleTrackRename,
  handleTracks,
} from '#/server/tracks/http'

const getSession = vi.fn()
vi.mock('#/lib/auth', () => ({ auth: { api: { getSession } } }))

const USER = '3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44'
const ID = '9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d'
const ITEM = '1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9'
const TOKEN = 'a-very-secret-engine-token-of-sufficient-length'
const env = { ENGINE_URL: 'http://engine.test:8000', ENGINE_TOKEN: TOKEN }
const signedIn = async () => ({ id: USER })
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

describe('tracks handlers', () => {
  it('answer 401 without a session and never call the engine', async () => {
    getSession.mockResolvedValue(null)
    const fetchFn = vi.fn()
    const deps = { fetchFn, env }
    const results = await Promise.all([
      handleTracks(request('GET'), deps),
      handleTrackCreate(request('POST', { name: 'a' }), deps),
      handleTrackRename(request('PATCH', { name: 'a' }), ID, deps),
      handleTrackDelete(request('DELETE'), ID, deps),
      handleEmphasis(request('PUT'), ID, 'skill', ITEM, true, deps),
      handlePreferences(request('PATCH', { locations: ['x'] }), ID, deps),
    ])
    expect(results.map((r) => r.status)).toEqual([401, 401, 401, 401, 401, 401])
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('forward to the engine with the user id and pass the answer through', async () => {
    getSession.mockResolvedValue({ user: { id: USER } })
    const fetchFn = vi.fn(async (url: string, init: RequestInit) => {
      void init
      return url.endsWith('/internal/tracks') && init.method === 'POST'
        ? reply({ id: ID }, 201)
        : reply({ ok: true })
    })
    const deps = { requireUser: signedIn, fetchFn, env }
    const created = await handleTrackCreate(
      request('POST', { name: 'a' }),
      deps,
    )
    expect(created.status).toBe(201)
    await handleEmphasis(request('PUT'), ID, 'skill', ITEM, true, deps)
    await handleEmphasis(request('DELETE'), ID, 'skill', ITEM, false, deps)
    const calls = fetchFn.mock.calls.map(([url, init]) => [init.method, url])
    expect(calls).toEqual([
      ['POST', 'http://engine.test:8000/internal/tracks'],
      [
        'PUT',
        `http://engine.test:8000/internal/tracks/${ID}/items/skill/${ITEM}`,
      ],
      [
        'DELETE',
        `http://engine.test:8000/internal/tracks/${ID}/items/skill/${ITEM}`,
      ],
    ])
  })

  it('a deleted track answers 204, a removed emphasis returns the track', async () => {
    const del = vi.fn(async () => new Response(null, { status: 204 }))
    const deps = { requireUser: signedIn, env }
    const gone = await handleTrackDelete(request('DELETE'), ID, {
      ...deps,
      fetchFn: del,
    })
    expect(gone.status).toBe(204)
    const track = vi.fn(async () => reply({ id: ID, emphasis: [] }))
    const off = await handleEmphasis(
      request('DELETE'),
      ID,
      'skill',
      ITEM,
      false,
      {
        ...deps,
        fetchFn: track,
      },
    )
    expect(off.status).toBe(200)
    expect(await off.json()).toEqual({ id: ID, emphasis: [] })
  })

  it('refuse a bad id or kind with 404 before calling the engine', async () => {
    const fetchFn = vi.fn()
    const deps = { requireUser: signedIn, fetchFn, env }
    expect(
      (await handleTrackDelete(request('DELETE'), 'nope', deps)).status,
    ).toBe(404)
    expect(
      (await handleEmphasis(request('PUT'), ID, 'widget', ITEM, true, deps))
        .status,
    ).toBe(404)
    expect(
      (await handleEmphasis(request('PUT'), ID, 'skill', 'nope', true, deps))
        .status,
    ).toBe(404)
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('turn an oversized body into the stable 422', async () => {
    const fetchFn = vi.fn()
    const big = request('POST', { name: 'x'.repeat(40000) })
    const r = await handleTrackCreate(big, {
      requireUser: signedIn,
      fetchFn,
      env,
    })
    expect(r.status).toBe(422)
    expect(fetchFn).not.toHaveBeenCalled()
  })
})

describe('preferences handler', () => {
  it('forwards a PATCH with the body and returns the track', async () => {
    const fetchFn = vi.fn(async (url: string, init: RequestInit) => {
      void url
      return reply({ id: ID, echoed: init.body })
    })
    const deps = { requireUser: signedIn, fetchFn, env }
    const r = await handlePreferences(
      request('PATCH', { locations: ['Nairobi'] }),
      ID,
      deps,
    )
    expect(r.status).toBe(200)
    expect(fetchFn.mock.calls[0][0]).toBe(
      `http://engine.test:8000/internal/tracks/${ID}/preferences`,
    )
    expect(fetchFn.mock.calls[0][1].method).toBe('PATCH')
  })

  it('refuses a bad id with 404 and an oversized body with 422', async () => {
    const fetchFn = vi.fn()
    const deps = { requireUser: signedIn, fetchFn, env }
    expect(
      (await handlePreferences(request('PATCH', {}), 'nope', deps)).status,
    ).toBe(404)
    const big = request('PATCH', { eligibility: 'x'.repeat(40000) })
    expect((await handlePreferences(big, ID, deps)).status).toBe(422)
    expect(fetchFn).not.toHaveBeenCalled()
  })
})
