import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  MAX_JOB_BODY_BYTES,
  handleJob,
  handleJobFetch,
  handleJobCreate,
  handleJobDelete,
  handleJobStatus,
  handleJobs,
} from '#/server/jobs/http'

const getSession = vi.fn()
vi.mock('#/lib/auth', () => ({ auth: { api: { getSession } } }))

const USER = '3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44'
const ID = '9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d'
const TOKEN = 'a-very-secret-engine-token-of-sufficient-length'
const env = { ENGINE_URL: 'http://engine.test:8000', ENGINE_TOKEN: TOKEN }
const signedIn = async () => ({ id: USER })
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })
const request = (method: string, body?: unknown, url = 'http://app.test/x') =>
  new Request(url, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: { 'content-type': 'application/json' },
  })

afterEach(() => {
  vi.restoreAllMocks()
  getSession.mockReset()
})

describe('jobs handlers', () => {
  it('answer 401 without a session and never call the engine', async () => {
    getSession.mockResolvedValue(null)
    const fetchFn = vi.fn()
    const deps = { fetchFn, env }
    const results = await Promise.all([
      handleJobs(request('GET'), deps),
      handleJobCreate(request('POST', { text: 'x' }), deps),
      handleJob(request('GET'), ID, deps),
      handleJobStatus(request('PATCH', {}), ID, deps),
      handleJobDelete(request('DELETE'), ID, deps),
      handleJobFetch(request('POST', { url: 'https://x.example/' }), deps),
    ])
    expect(results.map((r) => r.status)).toEqual([401, 401, 401, 401, 401, 401])
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('forward to the engine, passing the status filter and a 201', async () => {
    const fetchFn = vi.fn(async (url: string, init: RequestInit) => {
      void url
      return init.method === 'POST' ? reply({ id: ID }, 201) : reply([])
    })
    const deps = { requireUser: signedIn, fetchFn, env }
    const created = await handleJobCreate(
      request('POST', { company: 'A', title: 'T', text: 'x'.repeat(10) }),
      deps,
    )
    expect(created.status).toBe(201)
    await handleJobs(
      request('GET', undefined, 'http://app.test/api/jobs?status=dismissed'),
      deps,
    )
    await handleJobs(request('GET'), deps)
    expect(fetchFn.mock.calls.map(([url, init]) => [init.method, url])).toEqual(
      [
        ['POST', 'http://engine.test:8000/internal/jobs'],
        ['GET', 'http://engine.test:8000/internal/jobs?status=dismissed'],
        ['GET', 'http://engine.test:8000/internal/jobs'],
      ],
    )
  })

  it('answer 204 for a delete and refuse a bad id before the engine', async () => {
    const del = vi.fn(async () => new Response(null, { status: 204 }))
    const deps = { requireUser: signedIn, env }
    expect(
      (await handleJobDelete(request('DELETE'), ID, { ...deps, fetchFn: del }))
        .status,
    ).toBe(204)
    const never = vi.fn()
    for (const call of [
      handleJob(request('GET'), 'nope', { ...deps, fetchFn: never }),
      handleJobStatus(request('PATCH', {}), 'nope', {
        ...deps,
        fetchFn: never,
      }),
      handleJobDelete(request('DELETE'), 'nope', { ...deps, fetchFn: never }),
    ]) {
      expect((await call).status).toBe(404)
    }
    expect(never).not.toHaveBeenCalled()
  })

  it('allow a long posting but refuse one past the cap with a 422', async () => {
    const fetchFn = vi.fn(async () => reply({ id: ID }, 201))
    const deps = { requireUser: signedIn, fetchFn, env }
    const long = request('POST', { text: 'x'.repeat(100_000) })
    expect((await handleJobCreate(long, deps)).status).toBe(201)
    const big = request('POST', { text: 'x'.repeat(MAX_JOB_BODY_BYTES + 10) })
    expect((await handleJobCreate(big, deps)).status).toBe(422)
    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it('keep the short cap on other bodies', async () => {
    const fetchFn = vi.fn()
    const deps = { requireUser: signedIn, fetchFn, env }
    const r = await handleJobStatus(
      request('PATCH', { x: 'y'.repeat(40000) }),
      ID,
      deps,
    )
    expect(r.status).toBe(422)
    expect(fetchFn).not.toHaveBeenCalled()
  })
})

describe('fetch handler', () => {
  it('forwards the link, passes the answer and refusals through', async () => {
    const fetchFn = vi.fn(async (url: string, init: RequestInit) => {
      void url
      return String(init.body).includes('blocked')
        ? reply({ code: 'robots_disallowed', message: 'm' }, 422)
        : reply({
            text: 'Build apps.',
            title: null,
            finalUrl: 'u',
            truncated: false,
          })
    })
    const deps = { requireUser: signedIn, fetchFn, env }
    const ok = await handleJobFetch(
      request('POST', { url: 'https://x.example/j' }),
      deps,
    )
    expect(ok.status).toBe(200)
    expect((await ok.json()).text).toBe('Build apps.')
    const no = await handleJobFetch(
      request('POST', { url: 'https://blocked.example/' }),
      deps,
    )
    expect(no.status).toBe(422)
    expect((await no.json()).code).toBe('robots_disallowed')
    expect(fetchFn.mock.calls[0][0]).toBe(
      'http://engine.test:8000/internal/jobs/fetch',
    )
  })

  it('keeps the short body cap', async () => {
    const fetchFn = vi.fn()
    const deps = { requireUser: signedIn, fetchFn, env }
    const r = await handleJobFetch(
      request('POST', { url: 'x'.repeat(40000) }),
      deps,
    )
    expect(r.status).toBe(422)
    expect(fetchFn).not.toHaveBeenCalled()
  })
})
