import { createHash } from 'node:crypto'
import { and, eq } from 'drizzle-orm'
import { getDb } from '../db/client'
import type { Db } from '../db/client'
import { aiCache, usageEvent } from '../db/schema'
import { AiInputInvalidError, AiOutputInvalidError } from '../errors'
import { logger } from '../logger'
import { costUsd, createProvider, readTier } from './config'
import type { ModelSetting } from './config'
import { parseModelOutput } from './json'
import type { AiProvider } from './provider'
import type { AiTask } from './tasks'

export type RunOptions = {
  /** The authenticated user, taken from the session by the caller. */
  userId: string
  db?: Db
  env?: Record<string, string | undefined>
  /** Replaces the configured provider adapter (tests, future BYOK). */
  provider?: AiProvider
}

export type RunResult<TOutput> = {
  output: TOutput
  cacheHit: boolean
  promptVersion: string
  usageEventId: string
}

const JSON_INSTRUCTION =
  'Reply with a single JSON object and nothing else: no prose, no code fences.'

/** JSON with object keys sorted, so equal inputs always hash equally. */
export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(',')}]`
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== undefined)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`)
    return `{${entries.join(',')}}`
  }
  return value === undefined ? 'null' : JSON.stringify(value)
}

export function cacheKeyFor(
  task: string,
  promptVersion: string,
  model: string,
  input: unknown,
): string {
  return createHash('sha256')
    .update(canonicalJson({ task, promptVersion, model, input }))
    .digest('hex')
}

async function record(
  db: Db,
  values: typeof usageEvent.$inferInsert,
): Promise<string> {
  const rows = await db
    .insert(usageEvent)
    .values(values)
    .returning({ id: usageEvent.id })
  return rows[0].id
}

/**
 * Run one task for one user: validate input, reuse a cached result if there is
 * one, otherwise call the configured model, validate the JSON reply (one retry),
 * write a usage event for every response, and cache the validated output.
 * Prompts, inputs and outputs are never logged.
 */
export async function runTask<TInput, TOutput>(
  task: AiTask<TInput, TOutput>,
  input: unknown,
  options: RunOptions,
): Promise<RunResult<TOutput>> {
  const db = options.db ?? getDb()
  const env = options.env ?? process.env
  const started = Date.now()

  const parsedInput = task.input.safeParse(input)
  if (!parsedInput.success) throw new AiInputInvalidError()
  const taskInput = parsedInput.data

  const setting: ModelSetting = readTier(task.tier, env)
  const modelId = `${setting.provider}/${setting.model}`
  const base = {
    userId: options.userId,
    workflow: task.workflow,
    provider: setting.provider,
    model: setting.model,
    promptVersion: task.prompt.version,
  }
  const key = cacheKeyFor(task.name, task.prompt.version, modelId, taskInput)
  const useCache = task.cache !== false

  if (useCache) {
    const rows = await db
      .select({ output: aiCache.output })
      .from(aiCache)
      .where(and(eq(aiCache.userId, options.userId), eq(aiCache.cacheKey, key)))
    const cached =
      rows.length > 0 ? task.output.safeParse(rows[0].output) : null
    if (cached?.success) {
      const usageEventId = await record(db, {
        ...base,
        tokensIn: 0,
        tokensOut: 0,
        costUsd: '0',
        cacheHit: true,
      })
      logger.info('ai task', {
        task: task.name,
        provider: setting.provider,
        model: setting.model,
        cacheHit: true,
        durationMs: Date.now() - started,
      })
      return {
        output: cached.data,
        cacheHit: true,
        promptVersion: task.prompt.version,
        usageEventId,
      }
    }
  }

  const provider = options.provider ?? createProvider(setting, env)
  const system = `${task.prompt.system}\n\n${JSON_INSTRUCTION}`
  const userMessage = task.prompt.user(taskInput)
  let message = userMessage

  for (let attempt = 1; attempt <= 2; attempt++) {
    const response = await provider.complete({
      model: setting.model,
      system,
      user: message,
      timeoutMs: task.timeoutMs,
    })
    const cost = costUsd(response.tokensIn, response.tokensOut, setting.price)
    const usageEventId = await record(db, {
      ...base,
      tokensIn: response.tokensIn,
      tokensOut: response.tokensOut,
      costUsd: cost === null ? null : cost.toFixed(6),
      cacheHit: false,
    })

    const parsed = parseModelOutput(response.text, task.output)
    if (parsed.ok) {
      if (useCache) {
        await db
          .insert(aiCache)
          .values({
            userId: options.userId,
            cacheKey: key,
            task: task.name,
            promptVersion: task.prompt.version,
            output: parsed.value,
          })
          .onConflictDoUpdate({
            target: [aiCache.userId, aiCache.cacheKey],
            set: { output: parsed.value, createdAt: new Date() },
          })
      }
      logger.info('ai task', {
        task: task.name,
        provider: setting.provider,
        model: setting.model,
        cacheHit: false,
        attempts: attempt,
        durationMs: Date.now() - started,
      })
      return {
        output: parsed.value,
        cacheHit: false,
        promptVersion: task.prompt.version,
        usageEventId,
      }
    }

    logger.warn('ai output rejected', {
      task: task.name,
      provider: setting.provider,
      model: setting.model,
      attempt,
      reason: parsed.reason,
    })
    message = `${userMessage}\n\nYour previous reply was rejected: ${parsed.reason}. Reply again with only a valid JSON object.`
  }
  throw new AiOutputInvalidError()
}
