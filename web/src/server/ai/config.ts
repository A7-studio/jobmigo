import { AiNotConfiguredError } from '../errors'
import { OpenAiCompatibleProvider } from './openai-compatible'
import type { AiProvider } from './provider'

export type Tier = 'cheap' | 'strong'

type ProviderInfo = {
  /** Full chat-completions URL, from the provider's public documentation. */
  url: string
  keyEnv: string
  /** Only providers whose docs describe `response_format: json_object`. */
  jsonMode: boolean
}

/**
 * Confirmed against each provider's public docs when this was written:
 * DeepSeek documents `api.deepseek.com/chat/completions` and JSON output mode;
 * Moonshot documents `api.moonshot.ai/v1/chat/completions` and OpenRouter
 * `openrouter.ai/api/v1`, neither of which describes `response_format` there.
 */
export const PROVIDERS: Record<string, ProviderInfo> = {
  deepseek: {
    url: 'https://api.deepseek.com/chat/completions',
    keyEnv: 'DEEPSEEK_API_KEY',
    jsonMode: true,
  },
  moonshot: {
    url: 'https://api.moonshot.ai/v1/chat/completions',
    keyEnv: 'MOONSHOT_API_KEY',
    jsonMode: false,
  },
  openrouter: {
    url: 'https://openrouter.ai/api/v1/chat/completions',
    keyEnv: 'OPENROUTER_API_KEY',
    jsonMode: false,
  },
}

export type Price = { inputUsdPerMillion: number; outputUsdPerMillion: number }

export type ModelSetting = {
  provider: string
  model: string
  price: Price | null
}

type Env = Record<string, string | undefined>

const MODEL_VAR: Record<Tier, string> = {
  cheap: 'AI_CHEAP_MODEL',
  strong: 'AI_STRONG_MODEL',
}
const PRICE_VAR: Record<Tier, string> = {
  cheap: 'AI_CHEAP_PRICE',
  strong: 'AI_STRONG_PRICE',
}

function parsePrice(tier: Tier, raw: string | undefined): Price | null {
  if (!raw?.trim()) return null
  const rawParts = raw.split(',').map((part) => part.trim())
  const parts = rawParts.map((part) => (part === '' ? NaN : Number(part)))
  const [input, output] = parts
  if (
    parts.length !== 2 ||
    !Number.isFinite(input) ||
    !Number.isFinite(output) ||
    input < 0 ||
    output < 0
  ) {
    throw new AiNotConfiguredError(
      `${PRICE_VAR[tier]} must look like "inputUsdPerMillion,outputUsdPerMillion".`,
    )
  }
  return { inputUsdPerMillion: input, outputUsdPerMillion: output }
}

/** Read one tier's model setting from the environment, or fail visibly. */
export function readTier(tier: Tier, env: Env = process.env): ModelSetting {
  const raw = env[MODEL_VAR[tier]]?.trim()
  if (!raw) {
    throw new AiNotConfiguredError(
      `AI is not configured: set ${MODEL_VAR[tier]} (for example "deepseek/<model-id>").`,
    )
  }
  const slash = raw.indexOf('/')
  const provider = slash > 0 ? raw.slice(0, slash) : ''
  const model = slash > 0 ? raw.slice(slash + 1) : ''
  if (!model || !Object.hasOwn(PROVIDERS, provider)) {
    throw new AiNotConfiguredError(
      `${MODEL_VAR[tier]} must look like "provider/model-id" with a provider from: ${Object.keys(PROVIDERS).join(', ')}.`,
    )
  }
  return { provider, model, price: parsePrice(tier, env[PRICE_VAR[tier]]) }
}

type FetchLike = (input: string, init: RequestInit) => Promise<Response>

/** Build the provider adapter for a setting; the key is read at call time. */
export function createProvider(
  setting: ModelSetting,
  env: Env = process.env,
  fetchFn?: FetchLike,
): AiProvider {
  const info = PROVIDERS[setting.provider]
  const apiKey = env[info.keyEnv]?.trim()
  if (!apiKey) {
    throw new AiNotConfiguredError(
      `AI is not configured: set ${info.keyEnv} for the ${setting.provider} provider.`,
    )
  }
  return new OpenAiCompatibleProvider({
    name: setting.provider,
    url: info.url,
    apiKey,
    jsonMode: info.jsonMode,
    fetchFn,
  })
}

/** Cost in USD rounded to six decimals, or null when no price is configured. */
export function costUsd(
  tokensIn: number,
  tokensOut: number,
  price: Price | null,
): number | null {
  if (!price) return null
  const cost =
    (tokensIn / 1e6) * price.inputUsdPerMillion +
    (tokensOut / 1e6) * price.outputUsdPerMillion
  return Math.round(cost * 1e6) / 1e6
}
