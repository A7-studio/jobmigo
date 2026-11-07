import type { z } from 'zod'
import type { AI_WORKFLOWS } from '../db/schema'
import type { Tier } from './config'

export type Workflow = (typeof AI_WORKFLOWS)[number]

/**
 * A model task. The task name picks the tier (and so the model) through
 * configuration; the prompt `version` must change whenever the prompt text
 * does, because it is recorded in the ledger and part of the cache key.
 */
export type AiTask<TInput, TOutput> = {
  name: string
  workflow: Workflow
  tier: Tier
  prompt: {
    version: string
    system: string
    user: (input: TInput) => string
  }
  input: z.ZodType<TInput>
  output: z.ZodType<TOutput>
  /** Reuse cached results for identical input. Default true. */
  cache?: boolean
  /** Per-call time limit in milliseconds. Defaults to 60 seconds. */
  timeoutMs?: number
}

/** Identity helper that keeps the input and output types inferred. */
export function defineTask<TInput, TOutput>(
  task: AiTask<TInput, TOutput>,
): AiTask<TInput, TOutput> {
  return task
}
