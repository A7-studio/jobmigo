import { describe, expect, it } from 'vitest'
import { z } from 'zod'
import { extractJson, parseModelOutput } from '#/server/ai/json'
import { defineTask } from '#/server/ai/tasks'

const schema = z.object({ name: z.string(), years: z.number() })

describe('extractJson', () => {
  it('parses bare JSON', () => {
    expect(extractJson('{"a":1}')).toEqual({ ok: true, value: { a: 1 } })
  })

  it('parses a fenced block with or without a language tag', () => {
    expect(extractJson('Here:\n```json\n{"a":2}\n```\nDone')).toEqual({
      ok: true,
      value: { a: 2 },
    })
    expect(extractJson('```\n{"a":3}\n```')).toEqual({
      ok: true,
      value: { a: 3 },
    })
  })

  it('finds JSON inside surrounding prose', () => {
    expect(extractJson('Sure! {"a": 4} hope that helps')).toEqual({
      ok: true,
      value: { a: 4 },
    })
  })

  it('fails on invalid or empty replies', () => {
    expect(extractJson('no json here').ok).toBe(false)
    expect(extractJson('   ').ok).toBe(false)
    expect(extractJson('{"a": ').ok).toBe(false)
  })
})

describe('parseModelOutput', () => {
  it('returns the validated value', () => {
    expect(parseModelOutput('{"name":"Ada","years":3}', schema)).toEqual({
      ok: true,
      value: { name: 'Ada', years: 3 },
    })
  })

  it('reports invalid JSON without echoing the reply', () => {
    const result = parseModelOutput('secret-model-text', schema)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.reason).not.toContain('secret-model-text')
  })

  it('reports schema mismatches by path and code only', () => {
    const result = parseModelOutput(
      '{"name":"secret-value","years":"many"}',
      schema,
    )
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.reason).toContain('years')
      expect(result.reason).not.toContain('secret-value')
      expect(result.reason).not.toContain('many')
      expect(result.reason.length).toBeLessThan(200)
    }
  })
})

describe('parseModelOutput paths', () => {
  it('shows schema field names but never model-chosen keys', () => {
    const record = z.object({ skills: z.record(z.string(), z.number()) })
    const bad = parseModelOutput(
      '{"skills":{"cv secret name":"not a number"}}',
      record,
    )
    expect(bad.ok).toBe(false)
    if (!bad.ok) {
      expect(bad.reason).toContain('skills.*')
      expect(bad.reason).not.toContain('cv secret name')
    }
  })

  it('keeps known names through arrays and optional fields', () => {
    const nested = z.object({
      jobs: z.array(z.object({ title: z.string() })),
      note: z.object({ text: z.string() }).optional(),
    })
    const bad = parseModelOutput(
      '{"jobs":[{"title":"ok"},{"title":5}],"note":{"text":1}}',
      nested,
    )
    expect(bad.ok).toBe(false)
    if (!bad.ok) {
      expect(bad.reason).toContain('jobs.1.title')
      expect(bad.reason).toContain('note.text')
    }
  })
})

describe('defineTask', () => {
  it('keeps the definition as written', () => {
    const task = defineTask({
      name: 'demo',
      workflow: 'parse',
      tier: 'cheap',
      prompt: { version: 'v1', system: 's', user: (i: string) => i },
      input: z.string(),
      output: schema,
    })
    expect(task.prompt.version).toBe('v1')
  })
})
