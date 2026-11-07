import type { z } from 'zod'

export type ParseResult<T> =
  { ok: true; value: T } | { ok: false; reason: string }

const FENCE = /```(?:json)?\s*([\s\S]*?)```/i

function tryParse(text: string): { ok: true; value: unknown } | { ok: false } {
  try {
    return { ok: true, value: JSON.parse(text) as unknown }
  } catch {
    return { ok: false }
  }
}

/** Pull one JSON value out of a plain, fenced, or lightly wrapped reply. */
export function extractJson(
  text: string,
): { ok: true; value: unknown } | { ok: false } {
  const candidates: string[] = [text.trim()]
  const fenced = FENCE.exec(text)
  if (fenced) candidates.push(fenced[1].trim())
  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start !== -1 && end > start) candidates.push(text.slice(start, end + 1))
  for (const candidate of candidates) {
    if (!candidate) continue
    const parsed = tryParse(candidate)
    if (parsed.ok) return parsed
  }
  return { ok: false }
}

type SchemaLike = {
  shape?: Record<string, unknown>
  element?: unknown
  unwrap?: () => unknown
  def?: { type?: string }
}

const WRAPPERS = new Set([
  'optional',
  'nullable',
  'default',
  'prefault',
  'nonoptional',
  'readonly',
  'catch',
])

/**
 * Describe an issue path using only names that exist in the schema itself.
 * Keys the model chose (a record or catchall) are shown as `*`, so the text
 * can never carry model-generated content into logs or the retry prompt.
 */
function safePath(schema: unknown, path: PropertyKey[]): string {
  let current: unknown = schema
  const parts: string[] = []
  for (const segment of path) {
    while (
      current &&
      WRAPPERS.has((current as SchemaLike).def?.type ?? '') &&
      typeof (current as SchemaLike).unwrap === 'function'
    ) {
      current = (current as SchemaLike).unwrap?.()
    }
    const node = (current ?? {}) as SchemaLike
    if (typeof segment === 'number') {
      parts.push(String(segment))
      current = node.element
    } else if (
      typeof segment === 'string' &&
      node.shape &&
      Object.hasOwn(node.shape, segment)
    ) {
      parts.push(segment)
      current = node.shape[segment]
    } else {
      parts.push('*')
      current = undefined
    }
  }
  return parts.join('.')
}

/**
 * Parse a model reply against a schema. The failure reason is short and holds
 * only field paths and expected types, never the model's own text, so it is
 * safe to log and to send back for a retry.
 */
export function parseModelOutput<T>(
  text: string,
  schema: z.ZodType<T>,
): ParseResult<T> {
  const json = extractJson(text)
  if (!json.ok) return { ok: false, reason: 'the reply was not valid JSON' }
  const result = schema.safeParse(json.value)
  if (result.success) return { ok: true, value: result.data }
  const problems = result.error.issues
    .slice(0, 5)
    .map(
      (issue) => `${safePath(schema, issue.path) || '(root)'}: ${issue.code}`,
    )
  return {
    ok: false,
    reason: `the JSON did not match the schema (${problems.join('; ')})`,
  }
}
