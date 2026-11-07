import { describe, expect, it, vi } from 'vitest'
import { callEngine } from '#/server/engine/client'
import {
  DomainError,
  EngineNotConfiguredError,
  EngineUnavailableError,
} from '#/server/errors'
import { runWithRequestId } from '#/server/logger'

const USER = '3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44'
const TOKEN = 'a-very-secret-engine-token-of-sufficient-length'
const ENV = { ENGINE_URL: 'http://engine.test:8000', ENGINE_TOKEN: TOKEN }

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })

describe('callEngine', () => {
  it('sends the token, the user id and the request id', async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ userId: USER }))
    const result = await runWithRequestId('req-1', () =>
      callEngine('/internal/whoami', { userId: USER, env: ENV, fetchFn }),
    )
    expect(result).toEqual({ userId: USER })
    const [url, init] = fetchFn.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://engine.test:8000/internal/whoami')
    expect(init.headers).toEqual({
      authorization: `Bearer ${TOKEN}`,
      'x-user-id': USER,
      'x-request-id': 'req-1',
    })
    expect(init.method).toBe('GET')
    expect(init.redirect).toBe('error')
  })

  it('sends a JSON body and returns undefined for 204', async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }))
    const result = await callEngine('/internal/things', {
      userId: USER,
      method: 'POST',
      body: { a: 1 },
      env: ENV,
      fetchFn,
    })
    expect(result).toBeUndefined()
    const init = fetchFn.mock.calls[0][1] as RequestInit
    expect(init.body).toBe('{"a":1}')
    expect((init.headers as Record<string, string>)['content-type']).toBe(
      'application/json',
    )
  })

  it('wires the timeout through the abort signal', async () => {
    const fetchFn = vi.fn().mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => {
            reject(new Error('aborted'))
          })
        }),
    )
    const started = Date.now()
    await expect(
      callEngine('/internal/slow', {
        userId: USER,
        env: ENV,
        fetchFn,
        timeoutMs: 20,
      }),
    ).rejects.toBeInstanceOf(EngineUnavailableError)
    expect(Date.now() - started).toBeLessThan(2000)
    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it('honours a caller abort signal too', async () => {
    const controller = new AbortController()
    const fetchFn = vi.fn().mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => {
            reject(new Error('aborted'))
          })
          controller.abort()
        }),
    )
    await expect(
      callEngine('/internal/x', {
        userId: USER,
        env: ENV,
        fetchFn,
        signal: controller.signal,
      }),
    ).rejects.toBeInstanceOf(EngineUnavailableError)
  })

  it('maps a 401, a 5xx and a network failure to the stable error', async () => {
    for (const make of [
      () => Promise.resolve(json({ code: 'unauthorized', message: 'no' }, 401)),
      () => Promise.resolve(json({ detail: `boom ${TOKEN}` }, 500)),
      () => Promise.reject(new Error(`down ${TOKEN}`)),
    ]) {
      const error = await callEngine('/internal/x', {
        userId: USER,
        env: ENV,
        fetchFn: vi.fn().mockImplementation(make),
      }).catch((e: unknown) => e)
      expect(error).toBeInstanceOf(EngineUnavailableError)
      expect((error as Error).message).not.toContain(TOKEN)
      expect((error as Error).message).not.toContain('boom')
    }
  })

  it('passes a stable 4xx body from the engine through', async () => {
    const error = await callEngine('/internal/x', {
      userId: USER,
      env: ENV,
      fetchFn: vi
        .fn()
        .mockResolvedValue(
          json({ code: 'invalid_request', message: 'Bad id.' }, 400),
        ),
    }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(DomainError)
    expect(error).toMatchObject({ status: 400, code: 'invalid_request' })
    expect((error as Error).message).toBe('Bad id.')
  })

  it('does not pass through a 4xx body that is not the stable shape', async () => {
    for (const body of [
      { detail: 'something else' },
      { code: 'Bad Code!', message: 'x' },
      { code: 'ok_code', message: 'x'.repeat(500) },
    ]) {
      const error = await callEngine('/internal/x', {
        userId: USER,
        env: ENV,
        fetchFn: vi.fn().mockResolvedValue(json(body, 422)),
      }).catch((e: unknown) => e)
      expect(error).toBeInstanceOf(EngineUnavailableError)
    }
  })

  it('names only the missing variable when not configured', async () => {
    for (const [env, name] of [
      [{ ENGINE_TOKEN: TOKEN }, 'ENGINE_URL'],
      [{ ENGINE_URL: 'http://e' }, 'ENGINE_TOKEN'],
    ] as const) {
      const error = await callEngine('/internal/x', {
        userId: USER,
        env,
      }).catch((e: unknown) => e)
      expect(error).toBeInstanceOf(EngineNotConfiguredError)
      expect((error as Error).message).toContain(name)
      expect((error as Error).message).not.toContain(TOKEN)
    }
  })

  it('refuses a bad user id or a path outside /internal/', async () => {
    const fetchFn = vi.fn()
    await expect(
      callEngine('/internal/x', { userId: 'not-a-uuid', env: ENV, fetchFn }),
    ).rejects.toThrow('UUID')
    for (const path of [
      '/healthz',
      '/internal/../x',
      'http://evil/internal/x',
    ]) {
      await expect(
        callEngine(path, { userId: USER, env: ENV, fetchFn }),
      ).rejects.toThrow('/internal/')
    }
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it('never logs the token', async () => {
    const lines: string[] = []
    const log = vi.spyOn(console, 'log').mockImplementation((l: string) => {
      lines.push(l)
    })
    const fetchFn = vi.fn().mockResolvedValue(json({}, 500))
    await callEngine('/internal/x', { userId: USER, env: ENV, fetchFn }).catch(
      () => undefined,
    )
    log.mockRestore()
    expect(lines.join('\n')).toContain('engine call failed')
    expect(lines.join('\n')).not.toContain(TOKEN)
  })
})
