import { describe, expect, it } from 'vitest'
import {
  checkRows,
  evaluationFor,
  fitCopy,
  importanceLabel,
  pickTrack,
  sortRequirements,
  statusLabel,
} from '#/lib/fit-view'
import type { EvaluatedRequirement, Evaluation } from '#/lib/jobs-api'

const req = (
  need: string,
  status: EvaluatedRequirement['status'],
  importance: EvaluatedRequirement['importance'] = 'important',
): EvaluatedRequirement => ({
  need,
  importance,
  quote: need,
  status,
  evidence: [],
  note: '',
})

describe('words', () => {
  it('never says must and never shows a score', () => {
    expect(importanceLabel('important')).toBe('Looks important')
    expect(importanceLabel('nice')).toBe('Looks nice to have')
    expect(statusLabel('unknown')).toBe('Not shown in your profile')
  })
})

describe('checkRows', () => {
  it('words each state and keeps the order', () => {
    const rows = checkRows({
      salary: {
        status: 'below',
        postingMonthly: 800,
        floorMonthly: 1000,
        currency: 'USD',
        quote: null,
      },
      workMode: { status: 'matches', posting: 'remote' },
      region: { status: 'none_found', region: null },
    })
    expect(rows.map((r) => r.label)).toEqual(['Pay', 'Work mode', 'Region'])
    expect(rows[0]).toMatchObject({ value: 'Below your floor', tone: 'warn' })
    expect(rows[0].note).toContain('800 USD')
    expect(rows[1]).toMatchObject({
      tone: 'good',
      note: 'The posting says remote.',
    })
    expect(rows[2].tone).toBe('neutral')
  })

  it('is neutral when nothing is stated', () => {
    const rows = checkRows({
      salary: {
        status: 'unknown',
        postingMonthly: null,
        floorMonthly: null,
        currency: null,
        quote: null,
      },
      workMode: { status: 'unclear', posting: null },
      region: { status: 'unclear', region: null },
    })
    expect(rows.every((r) => r.tone === 'neutral')).toBe(true)
  })
})

describe('sortRequirements', () => {
  it('puts gaps first, then unknown, partial and met, important before nice', () => {
    const sorted = sortRequirements([
      req('a', 'met'),
      req('b', 'gap', 'nice'),
      req('c', 'gap'),
      req('d', 'unknown'),
      req('e', 'partial'),
    ]).map((r) => r.need)
    expect(sorted).toEqual(['c', 'b', 'd', 'e', 'a'])
  })

  it('does not change its input', () => {
    const input = [req('a', 'met'), req('b', 'gap')]
    sortRequirements(input)
    expect(input.map((r) => r.need)).toEqual(['a', 'b'])
  })
})

describe('tracks and results', () => {
  it('keeps a chosen track that exists, else the first', () => {
    const tracks = [{ id: 'x' }, { id: 'y' }]
    expect(pickTrack(tracks, 'y')).toBe('y')
    expect(pickTrack(tracks, 'gone')).toBe('x')
    expect(pickTrack([], null)).toBeNull()
  })

  it('finds the kept result for a track', () => {
    const list = [{ trackId: 'x' }, { trackId: 'y' }] as Evaluation[]
    expect(evaluationFor(list, 'y')).toBe(list[1])
    expect(evaluationFor(list, 'z')).toBeNull()
  })
})

describe('fitCopy', () => {
  it('has calm wording and never shows the code', () => {
    for (const code of [
      'no_confirmed_profile',
      'no_requirements',
      'ai_not_configured',
      'ai_unavailable',
      'ai_output_invalid',
      'not_found',
      'network',
      'weird_code',
    ]) {
      const copy = fitCopy(code)
      expect(copy.title + copy.body).not.toContain('_')
    }
    expect(fitCopy('ai_unavailable').action).toBe('retry')
    expect(fitCopy('no_confirmed_profile').action).toBe('profile')
  })
})
