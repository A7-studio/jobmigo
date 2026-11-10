import { describe, expect, it } from 'vitest'
import {
  MAX_CV_BYTES,
  POLL_LIMIT_MS,
  copyFor,
  screenFor,
  shouldKeepPolling,
  summarise,
  validateFile,
} from '#/lib/cv-view'
import type { CvRow } from '#/lib/cv-view'

const DOCX =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

const cv = (over: Partial<CvRow> = {}): CvRow => ({
  id: '9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d',
  filename: 'cv.pdf',
  mime: 'pdf',
  sizeBytes: 10,
  parseStatus: 'extracted',
  parseError: null,
  createdAt: '2026-11-10T09:00:00Z',
  ...over,
})

describe('validateFile', () => {
  const file = (name: string, size: number, type = '') => ({ name, size, type })

  it('accepts a PDF and a DOCX, by name, in any case', () => {
    expect(validateFile(file('CV.PDF', 10, 'application/pdf'))).toEqual({
      ok: true,
    })
    expect(validateFile(file('a.docx', 10, DOCX))).toEqual({ ok: true })
    expect(validateFile(file('a.pdf', 10, ''))).toEqual({ ok: true })
    expect(validateFile(file('a.pdf', 10, 'application/octet-stream'))).toEqual(
      { ok: true },
    )
  })

  it('refuses other types and a type that disagrees with the name', () => {
    for (const f of [
      file('a.txt', 10, 'text/plain'),
      file('a.doc', 10, 'application/msword'),
      file('a', 10),
      file('a.pdf', 10, 'text/plain'),
      file('a.pdf.exe', 10),
    ]) {
      expect(validateFile(f)).toEqual({
        ok: false,
        code: 'cv_unsupported_type',
      })
    }
  })

  it('refuses an empty file and one over 5 MiB, accepting exactly 5 MiB', () => {
    expect(validateFile(file('a.pdf', 0))).toEqual({
      ok: false,
      code: 'cv_empty',
    })
    expect(validateFile(file('a.pdf', MAX_CV_BYTES))).toEqual({ ok: true })
    expect(validateFile(file('a.pdf', MAX_CV_BYTES + 1))).toEqual({
      ok: false,
      code: 'cv_too_large',
    })
  })
})

describe('copyFor', () => {
  const codes = [
    'cv_empty',
    'cv_too_large',
    'cv_unsupported_type',
    'cv_unreadable',
    'unauthorized',
    'not_found',
    'ai_not_configured',
    'ai_unavailable',
    'engine_unavailable',
    'ai_output_invalid',
    'ai_input_invalid',
    'interrupted',
    'text_too_long',
    'no_profile_found',
    'internal',
    'network',
    'something_new',
  ]

  it('gives every code a title and body with no code or raw wording in it', () => {
    for (const code of codes) {
      const copy = copyFor(code)
      expect(copy.title.length).toBeGreaterThan(5)
      expect(copy.body.length).toBeGreaterThan(10)
      expect(copy.title + copy.body).not.toMatch(/[a-z]+_[a-z_]+/)
      expect(copy.title + copy.body).not.toMatch(/DEEPSEEK|AI_CHEAP|engine/i)
      expect(copy.retry || copy.another).toBe(true)
    }
  })

  it('offers a retry only where a retry can help', () => {
    for (const code of [
      'ai_unavailable',
      'engine_unavailable',
      'ai_output_invalid',
      'ai_input_invalid',
      'interrupted',
      'internal',
    ]) {
      expect(copyFor(code).retry).toBe(true)
    }
    for (const code of [
      'ai_not_configured',
      'text_too_long',
      'no_profile_found',
      'cv_unreadable',
    ]) {
      expect(copyFor(code).retry).toBe(false)
      expect(copyFor(code).another).toBe(true)
    }
  })
})

describe('screenFor', () => {
  it('maps no CV and each status', () => {
    expect(screenFor(null).kind).toBe('empty')
    expect(screenFor(cv({ parseStatus: 'extracted' })).kind).toBe('ready')
    expect(screenFor(cv({ parseStatus: 'parsing' })).kind).toBe('parsing')
    expect(screenFor(cv({ parseStatus: 'parsed' })).kind).toBe('parsed')
  })

  it('maps a failed CV to the copy for its code, and a missing code to a generic one', () => {
    const failed = screenFor(
      cv({ parseStatus: 'failed', parseError: 'text_too_long' }),
    )
    expect(failed.kind).toBe('failed')
    if (failed.kind === 'failed') {
      expect(failed.copy).toEqual(copyFor('text_too_long'))
    }
    const generic = screenFor(cv({ parseStatus: 'failed', parseError: null }))
    if (generic.kind === 'failed') {
      expect(generic.copy).toEqual(copyFor('internal'))
    }
  })
})

describe('shouldKeepPolling', () => {
  it('polls only while parsing and for at most three minutes', () => {
    expect(shouldKeepPolling('parsing', 0, 1_000)).toBe(true)
    expect(shouldKeepPolling('parsing', 0, POLL_LIMIT_MS - 1)).toBe(true)
    expect(shouldKeepPolling('parsing', 0, POLL_LIMIT_MS)).toBe(false)
    for (const status of ['extracted', 'parsed', 'failed'] as const) {
      expect(shouldKeepPolling(status, 0, 1)).toBe(false)
    }
  })
})

describe('summarise', () => {
  const draft = (over = {}) => ({
    headline: null,
    experiences: [],
    skills: [],
    achievements: [],
    projects: [],
    education: [],
    ...over,
  })

  it('lists only what was found, with singular and plural forms', () => {
    expect(
      summarise(
        draft({
          experiences: [1, 2, 3],
          skills: [1],
          education: [1, 2],
        }),
      ),
    ).toEqual(['3 roles', '1 skill', '2 education entries'])
    expect(summarise(draft())).toEqual([])
  })
})
