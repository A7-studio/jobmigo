import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  MAX_JOB_BODY_BYTES,
  safeName,
  handleJob,
  handleJobEvaluate,
  handleJobEvaluations,
  handleJobFetch,
  handleJobKit,
  handleJobKitEdit,
  handleJobKitExport,
  handleJobKits,
  handleJobScreen,
  handleJobScreens,
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
      handleJobScreen(request('POST'), ID, deps),
      handleJobScreens(request('GET'), ID, deps),
      handleJobEvaluate(request('POST', { trackId: ID }), ID, deps),
      handleJobEvaluations(request('GET'), ID, deps),
      handleJobKit(request('POST', { trackId: ID }), ID, deps),
      handleJobKits(request('GET'), ID, deps),
      handleJobKitEdit(request('PATCH', { path: 'summary' }), ID, ID, deps),
      handleJobKitExport(
        request('POST', { format: 'pdf', name: 'S' }),
        ID,
        ID,
        deps,
      ),
    ])
    expect(results.map((r) => r.status)).toEqual([
      401, 401, 401, 401, 401, 401, 401, 401, 401, 401, 401, 401, 401, 401,
    ])
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

describe('screen handlers', () => {
  it('forward only to the screen paths of that job, with the session user', async () => {
    const fetchFn = vi.fn(async (url: string, init: RequestInit) => {
      void url
      void init
      return reply([])
    })
    const deps = { requireUser: signedIn, fetchFn, env }
    expect((await handleJobScreen(request('POST'), ID, deps)).status).toBe(200)
    expect((await handleJobScreens(request('GET'), ID, deps)).status).toBe(200)
    expect(fetchFn.mock.calls.map(([url, init]) => [init.method, url])).toEqual(
      [
        ['POST', `http://engine.test:8000/internal/jobs/${ID}/screen`],
        ['GET', `http://engine.test:8000/internal/jobs/${ID}/screens`],
      ],
    )
    for (const [, init] of fetchFn.mock.calls) {
      expect(new Headers(init.headers).get('x-user-id')).toBe(USER)
    }
  })

  it('refuse a bad id before the engine', async () => {
    const never = vi.fn()
    const deps = { requireUser: signedIn, fetchFn: never, env }
    expect((await handleJobScreen(request('POST'), 'nope', deps)).status).toBe(
      404,
    )
    expect((await handleJobScreens(request('GET'), 'nope', deps)).status).toBe(
      404,
    )
    expect(never).not.toHaveBeenCalled()
  })

  it('pass an engine refusal through unchanged', async () => {
    const fetchFn = vi.fn(async () =>
      reply({ code: 'no_tracks', message: 'Create a track first.' }, 409),
    )
    const r = await handleJobScreen(request('POST'), ID, {
      requireUser: signedIn,
      fetchFn,
      env,
    })
    expect(r.status).toBe(409)
    expect(await r.json()).toEqual({
      code: 'no_tracks',
      message: 'Create a track first.',
    })
  })
})

describe('evaluation handlers', () => {
  it('forward only to the evaluation paths of that job, with the session user', async () => {
    const fetchFn = vi.fn(async (url: string, init: RequestInit) => {
      void url
      void init
      return reply([])
    })
    const deps = { requireUser: signedIn, fetchFn, env }
    expect(
      (await handleJobEvaluate(request('POST', { trackId: ID }), ID, deps))
        .status,
    ).toBe(200)
    expect((await handleJobEvaluations(request('GET'), ID, deps)).status).toBe(
      200,
    )
    expect(fetchFn.mock.calls.map(([url, init]) => [init.method, url])).toEqual(
      [
        ['POST', `http://engine.test:8000/internal/jobs/${ID}/evaluate`],
        ['GET', `http://engine.test:8000/internal/jobs/${ID}/evaluations`],
      ],
    )
    expect(fetchFn.mock.calls[0][1].body).toBe(JSON.stringify({ trackId: ID }))
    for (const [, init] of fetchFn.mock.calls) {
      expect(new Headers(init.headers).get('x-user-id')).toBe(USER)
    }
  })

  it('refuse a bad id before the engine', async () => {
    const never = vi.fn()
    const deps = { requireUser: signedIn, fetchFn: never, env }
    expect(
      (await handleJobEvaluate(request('POST', { trackId: ID }), 'nope', deps))
        .status,
    ).toBe(404)
    expect(
      (await handleJobEvaluations(request('GET'), 'nope', deps)).status,
    ).toBe(404)
    expect(never).not.toHaveBeenCalled()
  })

  it('refuse an oversized body with a 422 and never call the engine', async () => {
    const never = vi.fn()
    const r = await handleJobEvaluate(
      request('POST', { trackId: ID, x: 'y'.repeat(40_000) }),
      ID,
      { requireUser: signedIn, fetchFn: never, env },
    )
    expect(r.status).toBe(422)
    expect(never).not.toHaveBeenCalled()
  })

  it('pass an engine refusal through unchanged', async () => {
    const fetchFn = vi.fn(async () =>
      reply(
        {
          code: 'no_confirmed_profile',
          message: 'Confirm some of your profile first.',
        },
        409,
      ),
    )
    const r = await handleJobEvaluate(request('POST', { trackId: ID }), ID, {
      requireUser: signedIn,
      fetchFn,
      env,
    })
    expect(r.status).toBe(409)
    expect(await r.json()).toEqual({
      code: 'no_confirmed_profile',
      message: 'Confirm some of your profile first.',
    })
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

  it('forward the kit routes with the track and the user', async () => {
    const fetchFn = vi.fn(async (url: string, init: RequestInit) => {
      void url
      void init
      return reply([])
    })
    const deps = { requireUser: signedIn, fetchFn, env }
    const body = { trackId: ID, questions: ['Why us?'] }
    expect((await handleJobKit(request('POST', body), ID, deps)).status).toBe(
      200,
    )
    expect((await handleJobKits(request('GET'), ID, deps)).status).toBe(200)
    expect(
      (
        await handleJobKits(
          request('GET', undefined, `http://app.test/x?trackId=${ID}`),
          ID,
          deps,
        )
      ).status,
    ).toBe(200)
    expect(fetchFn.mock.calls.map(([url, init]) => [init.method, url])).toEqual(
      [
        ['POST', `http://engine.test:8000/internal/jobs/${ID}/kit`],
        ['GET', `http://engine.test:8000/internal/jobs/${ID}/kits`],
        [
          'GET',
          `http://engine.test:8000/internal/jobs/${ID}/kits?trackId=${ID}`,
        ],
      ],
    )
    expect(fetchFn.mock.calls[0][1].body).toBe(JSON.stringify(body))
    for (const [, init] of fetchFn.mock.calls) {
      expect(new Headers(init.headers).get('x-user-id')).toBe(USER)
    }
  })

  it('refuse a bad job or track id before the engine', async () => {
    const never = vi.fn()
    const deps = { requireUser: signedIn, fetchFn: never, env }
    expect(
      (await handleJobKit(request('POST', { trackId: ID }), 'nope', deps))
        .status,
    ).toBe(404)
    expect((await handleJobKits(request('GET'), 'nope', deps)).status).toBe(404)
    expect(
      (
        await handleJobKits(
          request('GET', undefined, 'http://app.test/x?trackId=nope'),
          ID,
          deps,
        )
      ).status,
    ).toBe(404)
    expect(never).not.toHaveBeenCalled()
  })

  it('forward a kit edit with the body and refuse bad ids before the engine', async () => {
    const fetchFn = vi.fn(async (url: string, init: RequestInit) => {
      void url
      void init
      return reply({ id: ID })
    })
    const deps = { requireUser: signedIn, fetchFn, env }
    const change = { path: 'summary', action: 'edit', text: 'My words.' }
    expect(
      (await handleJobKitEdit(request('PATCH', change), ID, ID, deps)).status,
    ).toBe(200)
    expect(fetchFn.mock.calls.map(([url, init]) => [init.method, url])).toEqual(
      [['PATCH', `http://engine.test:8000/internal/jobs/${ID}/kits/${ID}`]],
    )
    expect(fetchFn.mock.calls[0][1].body).toBe(JSON.stringify(change))
    const never = vi.fn()
    const guarded = { requireUser: signedIn, fetchFn: never, env }
    for (const [job, kit] of [
      ['nope', ID],
      [ID, 'nope'],
    ]) {
      expect(
        (await handleJobKitEdit(request('PATCH', change), job, kit, guarded))
          .status,
      ).toBe(404)
    }
    expect(never).not.toHaveBeenCalled()
  })

  describe('the export download', () => {
    const PDF = 'application/pdf'
    const bytes = new Uint8Array([37, 80, 68, 70, 45, 49])
    const b64 = Buffer.from(bytes).toString('base64')
    const ask = (reply_: Response, name = 'S') => {
      const fetchFn = vi.fn(async (url: string, init: RequestInit) => {
        void url
        void init
        return reply_
      })
      const deps = { requireUser: signedIn, fetchFn, env }
      return {
        fetchFn,
        run: () =>
          handleJobKitExport(
            request('POST', { format: 'pdf', name }),
            ID,
            ID,
            deps,
          ),
      }
    }

    it('turns the engine answer into a real, safe file response', async () => {
      const { run, fetchFn } = ask(
        reply({
          filename: 'José "Q" Müller/../x - CV.pdf',
          contentType: PDF,
          data: b64,
        }),
      )
      const r = await run()
      expect(r.status).toBe(200)
      expect(r.headers.get('content-type')).toBe(PDF)
      expect(r.headers.get('cache-control')).toBe('no-store')
      expect(r.headers.get('x-content-type-options')).toBe('nosniff')
      expect(r.headers.get('content-length')).toBe(String(bytes.byteLength))
      const disposition = r.headers.get('content-disposition') ?? ''
      expect(disposition.startsWith('attachment; filename="')).toBe(true)
      expect(disposition).not.toMatch(/["]{2}|\.\.\//)
      expect(decodeURIComponent(disposition.split("UTF-8''")[1])).toBe(
        'José Q Müller..x - CV.pdf',
      )
      expect(new Uint8Array(await r.arrayBuffer())).toEqual(bytes)
      expect(fetchFn.mock.calls[0][0]).toBe(
        `http://engine.test:8000/internal/jobs/${ID}/kits/${ID}/export`,
      )
      expect(fetchFn.mock.calls[0][1].method).toBe('POST')
    })

    it('cuts a long name by characters and never throws on an emoji', () => {
      const name = `a${'😀'.repeat(200)}`
      const cut = safeName(name)
      expect(Array.from(cut)).toHaveLength(150)
      expect(() => encodeURIComponent(cut)).not.toThrow()
      expect(() => encodeURIComponent(safeName('x\ud800y'))).not.toThrow()
      expect(safeName('x\ud800y')).toBe('xy')
      expect(safeName('a/b\\c"d%e;f')).toBe('abcdef')
      expect(safeName('   ')).toBe('document')
    })

    it('sends how many characters the PDF could not draw, and refuses nonsense', async () => {
      const ok = await ask(
        reply({ filename: 'a.pdf', contentType: PDF, data: b64, replaced: 4 }),
      ).run()
      expect(ok.status).toBe(200)
      expect(ok.headers.get('x-export-replaced')).toBe('4')
      const none = await ask(
        reply({ filename: 'a.pdf', contentType: PDF, data: b64 }),
      ).run()
      expect(none.headers.get('x-export-replaced')).toBe('0')
      for (const bad of [-1, 1.5, 'x', 5_000_000, null]) {
        const r = await ask(
          reply({
            filename: 'a.pdf',
            contentType: PDF,
            data: b64,
            replaced: bad,
          }),
        ).run()
        expect(r.status).toBe(502)
      }
    })

    it('passes an engine refusal through unchanged', async () => {
      const { run } = ask(
        reply(
          { code: 'needs_fixing', message: '1 statement still needs you.' },
          409,
        ),
      )
      const r = await run()
      expect(r.status).toBe(409)
      expect(await r.json()).toMatchObject({ code: 'needs_fixing' })
    })

    it('refuses an answer that is not a file it expects', async () => {
      for (const odd of [
        { filename: 'a.pdf', contentType: 'text/html', data: b64 },
        { filename: 'a.pdf', contentType: PDF, data: 'not base64!!' },
        { filename: 5, contentType: PDF, data: b64 },
        { filename: 'a.pdf', contentType: PDF },
        {
          filename: 'a.pdf',
          contentType: PDF,
          data: 'A'.repeat(8 * 1024 * 1024),
        },
      ]) {
        const r = await ask(reply(odd)).run()
        expect(r.status).toBe(502)
        expect(await r.json()).toEqual({
          code: 'unexpected',
          message: 'Something went wrong.',
        })
      }
    })

    it('refuses bad ids before the engine', async () => {
      const never = vi.fn()
      const deps = { requireUser: signedIn, fetchFn: never, env }
      for (const [job, kit] of [
        ['nope', ID],
        [ID, 'nope'],
      ]) {
        const r = await handleJobKitExport(
          request('POST', { format: 'pdf', name: 'S' }),
          job,
          kit,
          deps,
        )
        expect(r.status).toBe(404)
      }
      expect(never).not.toHaveBeenCalled()
    })
  })
})
