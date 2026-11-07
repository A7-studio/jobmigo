import { describe, expect, it, vi } from 'vitest'
import { OpenAiCompatibleProvider } from '#/server/ai/openai-compatible'
import { AiUnavailableError } from '#/server/errors'

const OK = {
  choices: [{ message: { content: '{"a":1}' } }],
  usage: { prompt_tokens: 12, completion_tokens: 5 },
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

function provider(
  fetchFn: (input: string, init: RequestInit) => Promise<Response>,
  jsonMode = true,
) {
  return new OpenAiCompatibleProvider({
    name: 'test',
    url: 'https://example.test/chat/completions',
    apiKey: 'secret-key',
    jsonMode,
    fetchFn,
    retryDelayMs: 0,
  })
}

const REQUEST = { model: 'm1', system: 'sys', user: 'hello' }

describe('OpenAiCompatibleProvider', () => {
  it('returns text and token counts from a good response', async () => {
    const fetchFn = vi.fn().mockResolvedValue(json(OK))
    const result = await provider(fetchFn).complete(REQUEST)
    expect(result).toEqual({ text: '{"a":1}', tokensIn: 12, tokensOut: 5 })
    const [url, init] = fetchFn.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('https://example.test/chat/completions')
    expect((init.headers as Record<string, string>).authorization).toBe(
      'Bearer secret-key',
    )
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    expect(body.model).toBe('m1')
    expect(body.response_format).toEqual({ type: 'json_object' })
  })

  it('omits response_format when the provider does not document it', async () => {
    const fetchFn = vi.fn().mockResolvedValue(json(OK))
    await provider(fetchFn, false).complete(REQUEST)
    const init = fetchFn.mock.calls[0][1] as RequestInit
    expect(JSON.parse(init.body as string)).not.toHaveProperty(
      'response_format',
    )
  })

  it('treats missing usage as zero tokens', async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValue(json({ choices: [{ message: { content: 'x' } }] }))
    expect(await provider(fetchFn).complete(REQUEST)).toEqual({
      text: 'x',
      tokensIn: 0,
      tokensOut: 0,
    })
  })

  it('retries once after a 429 and then succeeds', async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce(json({}, 429))
      .mockResolvedValueOnce(json(OK))
    const result = await provider(fetchFn).complete(REQUEST)
    expect(result.text).toBe('{"a":1}')
    expect(fetchFn).toHaveBeenCalledTimes(2)
  })

  it('fails after a persistent 500 with a generic error', async () => {
    const fetchFn = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(json({ error: 'secret provider detail' }, 500)),
      )
    const error = await provider(fetchFn)
      .complete(REQUEST)
      .catch((e: unknown) => e)
    expect(error).toBeInstanceOf(AiUnavailableError)
    expect((error as Error).message).not.toContain('secret')
    expect(fetchFn).toHaveBeenCalledTimes(2)
  })

  it('retries a network error or timeout once, then fails', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('timeout'))
    await expect(provider(fetchFn).complete(REQUEST)).rejects.toBeInstanceOf(
      AiUnavailableError,
    )
    expect(fetchFn).toHaveBeenCalledTimes(2)
  })

  it('does not retry a 401 or other client error', async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({}, 401))
    await expect(provider(fetchFn).complete(REQUEST)).rejects.toBeInstanceOf(
      AiUnavailableError,
    )
    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it('returns empty text with the tokens when the reply has no content', async () => {
    for (const body of [
      { choices: [], usage: { prompt_tokens: 9, completion_tokens: 3 } },
      {
        choices: [{ message: { content: null } }],
        usage: { prompt_tokens: 9, completion_tokens: 3 },
      },
    ]) {
      const fetchFn = vi.fn().mockResolvedValue(json(body))
      expect(await provider(fetchFn).complete(REQUEST)).toEqual({
        text: '',
        tokensIn: 9,
        tokensOut: 3,
      })
      expect(fetchFn).toHaveBeenCalledTimes(1)
    }
  })

  it('fails when the body is not JSON, without retrying', async () => {
    const fetchFn = vi.fn().mockResolvedValue(new Response('<html>oops</html>'))
    await expect(provider(fetchFn).complete(REQUEST)).rejects.toBeInstanceOf(
      AiUnavailableError,
    )
    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it('aborts a call that outlives its time limit', async () => {
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
      provider(fetchFn).complete({ ...REQUEST, timeoutMs: 20 }),
    ).rejects.toBeInstanceOf(AiUnavailableError)
    expect(fetchFn).toHaveBeenCalledTimes(2)
    expect(Date.now() - started).toBeLessThan(2000)
  })

  it('never logs the prompt, the key or the reply', async () => {
    const lines: string[] = []
    const spies = [
      vi.spyOn(console, 'log').mockImplementation((l: string) => {
        lines.push(l)
      }),
      vi.spyOn(console, 'error').mockImplementation((l: string) => {
        lines.push(l)
      }),
    ]
    const fetchFn = vi
      .fn()
      .mockResolvedValue(json({ error: 'reply-detail' }, 500))
    await provider(fetchFn)
      .complete({ model: 'm', system: 'sys-text', user: 'cv-text' })
      .catch(() => undefined)
    spies.forEach((spy) => spy.mockRestore())
    const logged = lines.join('\n')
    expect(logged).toContain('ai provider call failed')
    for (const secret of [
      'cv-text',
      'sys-text',
      'secret-key',
      'reply-detail',
    ]) {
      expect(logged).not.toContain(secret)
    }
  })
})
