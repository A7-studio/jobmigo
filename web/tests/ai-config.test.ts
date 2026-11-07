import { describe, expect, it } from 'vitest'
import { costUsd, createProvider, readTier } from '#/server/ai/config'
import { AiNotConfiguredError } from '#/server/errors'

function configError(run: () => unknown): string {
  try {
    run()
  } catch (error) {
    expect(error).toBeInstanceOf(AiNotConfiguredError)
    return (error as Error).message
  }
  throw new Error('expected a configuration error')
}

describe('readTier', () => {
  it('reads provider, model and price', () => {
    const setting = readTier('cheap', {
      AI_CHEAP_MODEL: 'deepseek/some-model',
      AI_CHEAP_PRICE: '0.3, 1.2',
    })
    expect(setting).toEqual({
      provider: 'deepseek',
      model: 'some-model',
      price: { inputUsdPerMillion: 0.3, outputUsdPerMillion: 1.2 },
    })
  })

  it('keeps slashes inside the model id', () => {
    const setting = readTier('strong', {
      AI_STRONG_MODEL: 'openrouter/vendor/model-x',
    })
    expect(setting.provider).toBe('openrouter')
    expect(setting.model).toBe('vendor/model-x')
    expect(setting.price).toBeNull()
  })

  it('names the variable when the tier is not set', () => {
    expect(configError(() => readTier('cheap', {}))).toContain('AI_CHEAP_MODEL')
  })

  it('rejects malformed settings without echoing the value', () => {
    const message = configError(() =>
      readTier('cheap', { AI_CHEAP_MODEL: 'nonsense-value' }),
    )
    expect(message).toContain('AI_CHEAP_MODEL')
    expect(message).not.toContain('nonsense-value')
    expect(
      configError(() => readTier('cheap', { AI_CHEAP_MODEL: 'unknown/m' })),
    ).toContain('deepseek')
    expect(
      configError(() => readTier('cheap', { AI_CHEAP_MODEL: 'deepseek/' })),
    ).toContain('AI_CHEAP_MODEL')
  })

  it('rejects a malformed price', () => {
    for (const price of ['1', 'a,b', '-1,2', '1,2,3', '5,', ',5', ',']) {
      expect(
        configError(() =>
          readTier('cheap', {
            AI_CHEAP_MODEL: 'deepseek/m',
            AI_CHEAP_PRICE: price,
          }),
        ),
      ).toContain('AI_CHEAP_PRICE')
    }
  })
})

describe('createProvider', () => {
  it('names the missing key variable, never a value', () => {
    const message = configError(() =>
      createProvider({ provider: 'moonshot', model: 'm', price: null }, {}),
    )
    expect(message).toContain('MOONSHOT_API_KEY')
  })

  it('builds a provider when the key is present', () => {
    const provider = createProvider(
      { provider: 'deepseek', model: 'm', price: null },
      { DEEPSEEK_API_KEY: 'secret-key' },
    )
    expect(provider.name).toBe('deepseek')
  })
})

describe('costUsd', () => {
  it('computes cost from tokens and rounds to six decimals', () => {
    const price = { inputUsdPerMillion: 0.3, outputUsdPerMillion: 1.2 }
    expect(costUsd(1_000_000, 500_000, price)).toBe(0.9)
    expect(costUsd(1000, 1000, price)).toBe(0.0015)
    expect(costUsd(1, 0, price)).toBe(0)
    expect(costUsd(0, 0, price)).toBe(0)
  })

  it('is null without a price', () => {
    expect(costUsd(100, 100, null)).toBeNull()
  })
})
