import { AiUnavailableError } from '../errors'
import { logger } from '../logger'
import type { AiProvider, AiRequest, AiResponse } from './provider'

type FetchLike = (input: string, init: RequestInit) => Promise<Response>

export type OpenAiCompatibleOptions = {
  name: string
  /** Full chat-completions URL. */
  url: string
  apiKey: string
  /** Send `response_format: json_object`; only for providers that document it. */
  jsonMode: boolean
  fetchFn?: FetchLike
  retryDelayMs?: number
}

const DEFAULT_TIMEOUT_MS = 60_000

function isTransient(status: number): boolean {
  return status === 429 || status >= 500
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
    ? Math.floor(value)
    : 0
}

/**
 * Talks to any OpenAI-compatible chat-completions API with plain `fetch`.
 * Retries once on a timeout, network error, 429 or 5xx. Never logs prompts,
 * replies, headers or keys: only the provider, status and duration.
 */
export class OpenAiCompatibleProvider implements AiProvider {
  readonly name: string
  private readonly options: OpenAiCompatibleOptions
  private readonly fetchFn: FetchLike

  constructor(options: OpenAiCompatibleOptions) {
    this.options = options
    this.name = options.name
    this.fetchFn = options.fetchFn ?? fetch
  }

  async complete(request: AiRequest): Promise<AiResponse> {
    const started = Date.now()
    for (let attempt = 1; attempt <= 2; attempt++) {
      const outcome = await this.attempt(request)
      if (outcome.kind === 'ok') return outcome.response
      logger.warn('ai provider call failed', {
        provider: this.name,
        status: outcome.status,
        attempt,
        durationMs: Date.now() - started,
      })
      if (!outcome.transient || attempt === 2) break
      await wait(this.options.retryDelayMs ?? 500)
    }
    throw new AiUnavailableError()
  }

  private async attempt(
    request: AiRequest,
  ): Promise<
    | { kind: 'ok'; response: AiResponse }
    | { kind: 'failed'; status: number | 'network'; transient: boolean }
  > {
    const body: Record<string, unknown> = {
      model: request.model,
      messages: [
        { role: 'system', content: request.system },
        { role: 'user', content: request.user },
      ],
    }
    if (this.options.jsonMode) body.response_format = { type: 'json_object' }

    let response: Response
    try {
      response = await this.fetchFn(this.options.url, {
        method: 'POST',
        headers: {
          authorization: `Bearer ${this.options.apiKey}`,
          'content-type': 'application/json',
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(request.timeoutMs ?? DEFAULT_TIMEOUT_MS),
      })
    } catch {
      return { kind: 'failed', status: 'network', transient: true }
    }
    if (!response.ok) {
      return {
        kind: 'failed',
        status: response.status,
        transient: isTransient(response.status),
      }
    }

    let payload: unknown
    try {
      payload = await response.json()
    } catch {
      return { kind: 'failed', status: response.status, transient: false }
    }
    if (!payload || typeof payload !== 'object') {
      return { kind: 'failed', status: response.status, transient: false }
    }
    const data = payload as {
      choices?: { message?: { content?: unknown } }[]
      usage?: { prompt_tokens?: unknown; completion_tokens?: unknown }
    }
    // A reply with no text (a refusal, a cutoff) is still billed. Return empty
    // text with the tokens so the gateway records the usage and rejects the
    // reply as invalid, instead of losing the spend.
    const content = data.choices?.[0]?.message?.content
    const text = typeof content === 'string' ? content : ''
    return {
      kind: 'ok',
      response: {
        text,
        tokensIn: count(data.usage?.prompt_tokens),
        tokensOut: count(data.usage?.completion_tokens),
      },
    }
  }
}
