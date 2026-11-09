import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  MAX_CV_BYTES,
  handleDelete,
  handleDownload,
  handleList,
  handleParse,
  handleProfile,
  handleStatus,
  handleUpload,
} from '#/server/cv/http'
import { UnauthorizedError } from '#/server/errors'

const getSession = vi.fn()
vi.mock('#/lib/auth', () => ({ auth: { api: { getSession } } }))

const USER = '3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44'
const CV = '9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d'
const TOKEN = 'a-very-secret-engine-token-of-sufficient-length'
const env = { ENGINE_URL: 'http://engine.test:8000', ENGINE_TOKEN: TOKEN }
const signedIn = async () => ({ id: USER })
const MIB = 1024 * 1024

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })

type Fetch = (url: string, init: RequestInit) => Promise<Response>

function upload(
  body: BodyInit | ReadableStream<Uint8Array> | null,
  headers: Record<string, string> = {},
) {
  return new Request('http://app.test/api/cv', {
    method: 'POST',
    body,
    headers,
    // @ts-expect-error Node needs `duplex` for a streamed request body
    duplex: 'half',
  })
}

function chunked(count: number, size: number): ReadableStream<Uint8Array> {
  let sent = 0
  return new ReadableStream({
    pull(controller) {
      if (sent === count) return controller.close()
      sent += 1
      controller.enqueue(new Uint8Array(size))
    },
  })
}

async function drain(body: unknown): Promise<number> {
  const reader = (body as ReadableStream<Uint8Array>).getReader()
  let total = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) return total
    total += value.byteLength
  }
}

const logged: string[] = []
function captureLogs() {
  for (const method of ['log', 'warn', 'error'] as const) {
    vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
      logged.push(args.map(String).join(' '))
    })
  }
}
afterEach(() => {
  vi.restoreAllMocks()
  getSession.mockReset()
  logged.length = 0
})

describe('without a session', () => {
  it('every handler answers 401 and never calls the engine', async () => {
    getSession.mockResolvedValue(null)
    const fetchFn = vi.fn()
    const deps = { fetchFn, env }
    const request = (method: string) =>
      new Request('http://app.test/x', { method })
    const results = await Promise.all([
      handleUpload(upload(new Uint8Array(3)), deps),
      handleList(request('GET'), deps),
      handleDownload(request('GET'), CV, deps),
      handleDelete(request('DELETE'), CV, deps),
      handleStatus(request('GET'), CV, deps),
      handleParse(request('POST'), CV, deps),
      handleProfile(request('GET'), CV, deps),
    ])
    for (const response of results) {
      expect(response.status).toBe(401)
      expect(await response.json()).toEqual({
        code: 'unauthorized',
        message: 'Sign in to continue.',
      })
    }
    expect(fetchFn).not.toHaveBeenCalled()
  })
})

describe('upload', () => {
  it('streams the body to the engine as the session user and returns 201', async () => {
    const created = { id: CV, filename: 'cv.pdf', mime: 'pdf' }
    const fetchFn = vi.fn<Fetch>(async (_url, init) => {
      expect(await drain(init.body)).toBe(3 * 1000)
      return jsonResponse(created, 201)
    })
    const response = await handleUpload(
      upload(chunked(3, 1000), { 'x-filename': 'Zo%C3%AB%20CV.pdf' }),
      { requireUser: signedIn, fetchFn, env },
    )
    expect(response.status).toBe(201)
    expect(await response.json()).toEqual(created)
    const [url, init] = fetchFn.mock.calls[0]
    expect(url).toBe('http://engine.test:8000/internal/cv')
    expect(init.method).toBe('POST')
    expect(init.headers).toMatchObject({
      authorization: `Bearer ${TOKEN}`,
      'x-user-id': USER,
      'x-filename': 'Zo%C3%AB%20CV.pdf',
      'content-type': 'application/octet-stream',
    })
    expect((init as { duplex?: string }).duplex).toBe('half')
  })

  it('takes the user from the session, never from the request', async () => {
    const fetchFn = vi.fn<Fetch>(async (_url, init) => {
      await drain(init.body)
      return jsonResponse({}, 201)
    })
    await handleUpload(
      upload(chunked(1, 10), {
        'x-user-id': 'attacker',
        authorization: 'Bearer nope',
      }),
      { requireUser: signedIn, fetchFn, env },
    )
    const [, init] = fetchFn.mock.calls[0]
    expect(init.headers).toMatchObject({
      'x-user-id': USER,
      authorization: `Bearer ${TOKEN}`,
    })
  })

  it('drops a filename header that is not printable ASCII', async () => {
    const fetchFn = vi.fn<Fetch>(async (_url, init) => {
      await drain(init.body)
      return jsonResponse({}, 201)
    })
    await handleUpload(
      upload(chunked(1, 10), { 'x-filename': 'a'.repeat(2000) }),
      {
        requireUser: signedIn,
        fetchFn,
        env,
      },
    )
    expect(fetchFn.mock.calls[0][1].headers).not.toHaveProperty('x-filename')
  })

  it('refuses an over-limit Content-Length without calling the engine', async () => {
    const fetchFn = vi.fn()
    const response = await handleUpload(
      upload(new Uint8Array(10), {
        'content-length': String(MAX_CV_BYTES + 1),
      }),
      { requireUser: signedIn, fetchFn, env },
    )
    expect(response.status).toBe(413)
    expect((await response.json()).code).toBe('cv_too_large')
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('stops a chunked body at the limit and answers 413, not an outage', async () => {
    let read = 0
    const fetchFn = vi.fn<Fetch>(async (_url, init) => {
      const reader = (init.body as ReadableStream<Uint8Array>).getReader()
      for (;;) {
        const { done, value } = await reader.read() // throws when the stream is cut
        if (done) break
        read += value.byteLength
      }
      return jsonResponse({}, 201)
    })
    const response = await handleUpload(upload(chunked(40, MIB)), {
      requireUser: signedIn,
      fetchFn,
      env,
    })
    expect(response.status).toBe(413)
    expect((await response.json()).code).toBe('cv_too_large')
    expect(read).toBeLessThanOrEqual(MAX_CV_BYTES)
  })

  it.each([
    [413, 'cv_too_large'],
    [415, 'cv_unsupported_type'],
    [422, 'cv_unreadable'],
  ])('passes the engine %i %s through unchanged', async (status, code) => {
    const fetchFn = vi.fn<Fetch>(async (_url, init) => {
      await drain(init.body)
      return jsonResponse({ code, message: 'Nope.' }, status)
    })
    const response = await handleUpload(upload(chunked(1, 10)), {
      requireUser: signedIn,
      fetchFn,
      env,
    })
    expect(response.status).toBe(status)
    expect(await response.json()).toEqual({ code, message: 'Nope.' })
  })

  it('reports an engine outage as engine_unavailable', async () => {
    const fetchFn = vi.fn<Fetch>(async (_url, init) => {
      await drain(init.body)
      return jsonResponse({ code: 'storage_unavailable', message: 'x' }, 502)
    })
    const response = await handleUpload(upload(chunked(1, 10)), {
      requireUser: signedIn,
      fetchFn,
      env,
    })
    expect(response.status).toBe(502)
    expect((await response.json()).code).toBe('engine_unavailable')
  })
})

describe('list, download and delete', () => {
  it('lists through the engine for the session user', async () => {
    const fetchFn = vi.fn<Fetch>(async () => jsonResponse({ items: [] }))
    const response = await handleList(new Request('http://app.test/api/cv'), {
      requireUser: signedIn,
      fetchFn,
      env,
    })
    expect(await response.json()).toEqual({ items: [] })
    expect(response.headers.get('cache-control')).toBe('no-store')
    expect(fetchFn.mock.calls[0][0]).toBe('http://engine.test:8000/internal/cv')
    expect(fetchFn.mock.calls[0][1].headers).toMatchObject({
      'x-user-id': USER,
    })
  })

  it('answers download with a 302 to the engine link', async () => {
    const link = 'http://localhost:9100/jobmigo/cv/x?X-Amz-Signature=abc'
    const fetchFn = vi.fn<Fetch>(async () =>
      jsonResponse({ url: link, expiresInSeconds: 300 }),
    )
    const response = await handleDownload(
      new Request('http://app.test/x'),
      CV,
      {
        requireUser: signedIn,
        fetchFn,
        env,
      },
    )
    expect(response.status).toBe(302)
    expect(response.headers.get('location')).toBe(link)
    expect(response.headers.get('cache-control')).toBe('no-store')
    expect(fetchFn.mock.calls[0][0]).toBe(
      `http://engine.test:8000/internal/cv/${CV}/download`,
    )
  })

  it.each([
    ['not a url', { url: 'javascript:alert(1)' }],
    ['no url', {}],
  ])('never redirects to %s', async (_name, body) => {
    const fetchFn = vi.fn<Fetch>(async () => jsonResponse(body))
    const response = await handleDownload(
      new Request('http://app.test/x'),
      CV,
      {
        requireUser: signedIn,
        fetchFn,
        env,
      },
    )
    expect(response.status).toBe(500)
    expect(response.headers.get('location')).toBeNull()
  })

  it('deletes with 204', async () => {
    const fetchFn = vi.fn<Fetch>(
      async () => new Response(null, { status: 204 }),
    )
    const response = await handleDelete(new Request('http://app.test/x'), CV, {
      requireUser: signedIn,
      fetchFn,
      env,
    })
    expect(response.status).toBe(204)
    expect(fetchFn.mock.calls[0][1].method).toBe('DELETE')
  })

  it('answers 404 for a malformed id without calling the engine', async () => {
    const fetchFn = vi.fn()
    for (const handle of [handleDownload, handleDelete]) {
      const response = await handle(new Request('http://app.test/x'), '../x', {
        requireUser: signedIn,
        fetchFn,
        env,
      })
      expect(response.status).toBe(404)
    }
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it("passes the engine's 404 through for download and delete", async () => {
    const fetchFn = vi.fn<Fetch>(async () =>
      jsonResponse({ code: 'not_found', message: 'Not found.' }, 404),
    )
    const deps = { requireUser: signedIn, fetchFn, env }
    for (const handle of [handleDownload, handleDelete]) {
      const response = await handle(new Request('http://app.test/x'), CV, deps)
      expect(response.status).toBe(404)
      expect(await response.json()).toEqual({
        code: 'not_found',
        message: 'Not found.',
      })
    }
  })
})

describe('logging', () => {
  it('never logs the filename, the signed link or the token', async () => {
    captureLogs()
    const link = 'http://localhost:9100/jobmigo/cv/x?X-Amz-Signature=sig-secret'
    const fetchFn = vi.fn<Fetch>(async (url, init) => {
      if (init.body) await drain(init.body)
      if (url.endsWith('/download')) return jsonResponse({ url: link })
      return jsonResponse({ code: 'cv_unreadable', message: 'No.' }, 422)
    })
    const deps = { requireUser: signedIn, fetchFn, env }
    await handleUpload(
      upload(chunked(1, 10), { 'x-filename': 'Jane-Secret-Name.pdf' }),
      deps,
    )
    await handleDownload(new Request('http://app.test/x'), CV, deps)
    await handleUpload(
      upload(chunked(40, MIB), { 'x-filename': 'Jane-Secret-Name.pdf' }),
      deps,
    )
    await handleUpload(upload(null), {
      requireUser: async () => {
        throw new UnauthorizedError()
      },
      fetchFn,
      env,
    })
    const output = logged.join('\n')
    expect(output).not.toContain('Jane-Secret-Name')
    expect(output).not.toContain('sig-secret')
    expect(output).not.toContain(TOKEN)
  })
})

describe('status, parse and profile', () => {
  const request = (method: string) =>
    new Request('http://app.test/x', { method })

  it('forwards each call to the matching engine path for the session user', async () => {
    const fetchFn = vi.fn<Fetch>(async () => jsonResponse({ ok: true }))
    const deps = { requireUser: signedIn, fetchFn, env }
    await handleStatus(request('GET'), CV, deps)
    await handleParse(request('POST'), CV, deps)
    await handleProfile(request('GET'), CV, deps)
    expect(fetchFn.mock.calls.map(([url, init]) => [init.method, url])).toEqual(
      [
        ['GET', `http://engine.test:8000/internal/cv/${CV}`],
        ['POST', `http://engine.test:8000/internal/cv/${CV}/parse`],
        ['GET', `http://engine.test:8000/internal/cv/${CV}/profile`],
      ],
    )
    for (const [, init] of fetchFn.mock.calls) {
      expect(init.headers).toMatchObject({ 'x-user-id': USER })
    }
  })

  it('answers parse 202 while it runs and 200 once parsed', async () => {
    const deps = (parseStatus: string) => ({
      requireUser: signedIn,
      fetchFn: vi.fn<Fetch>(async () =>
        jsonResponse({ id: CV, parseStatus, parseError: null }),
      ),
      env,
    })
    const running = await handleParse(request('POST'), CV, deps('parsing'))
    expect(running.status).toBe(202)
    expect((await running.json()).parseStatus).toBe('parsing')
    const done = await handleParse(request('POST'), CV, deps('parsed'))
    expect(done.status).toBe(200)
    expect(done.headers.get('cache-control')).toBe('no-store')
  })

  it('answers 404 for a malformed id without calling the engine', async () => {
    const fetchFn = vi.fn()
    for (const handle of [handleStatus, handleParse, handleProfile]) {
      const response = await handle(request('GET'), '../x', {
        requireUser: signedIn,
        fetchFn,
        env,
      })
      expect(response.status).toBe(404)
    }
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it("passes the engine's stable client errors through", async () => {
    const fetchFn = vi.fn<Fetch>(async () =>
      jsonResponse({ code: 'not_found', message: 'Not found.' }, 404),
    )
    const deps = { requireUser: signedIn, fetchFn, env }
    for (const handle of [handleStatus, handleParse, handleProfile]) {
      const response = await handle(request('GET'), CV, deps)
      expect(response.status).toBe(404)
      expect(await response.json()).toEqual({
        code: 'not_found',
        message: 'Not found.',
      })
    }
  })

  it('reports an engine 5xx, including ai_not_configured, as engine_unavailable', async () => {
    const fetchFn = vi.fn<Fetch>(async () =>
      jsonResponse(
        { code: 'ai_not_configured', message: 'AI is not configured: set X.' },
        503,
      ),
    )
    const response = await handleParse(request('POST'), CV, {
      requireUser: signedIn,
      fetchFn,
      env,
    })
    expect(response.status).toBe(502)
    const body = await response.json()
    expect(body.code).toBe('engine_unavailable')
    expect(JSON.stringify(body)).not.toContain('AI is not configured')
  })
})
