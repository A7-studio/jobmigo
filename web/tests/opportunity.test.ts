import { describe, expect, it } from 'vitest'
import {
  OPPORTUNITY_KINDS,
  isKind,
  kindDocument,
  kindLabel,
} from '#/lib/opportunity'

describe('opportunity kinds', () => {
  it('has the three kinds in order with plain labels', () => {
    expect([...OPPORTUNITY_KINDS]).toEqual(['job', 'gig', 'ai_training'])
    expect(OPPORTUNITY_KINDS.map(kindLabel)).toEqual([
      'Job',
      'Freelance gig',
      'AI training role',
    ])
  })

  it('writes a cover letter for a job and a proposal for the others', () => {
    expect(kindDocument('job')).toBe('cover letter')
    expect(kindDocument('gig')).toBe('proposal')
    expect(kindDocument('ai_training')).toBe('proposal')
  })

  it('accepts only the three words', () => {
    expect(isKind('gig')).toBe(true)
    expect(isKind('side')).toBe(false)
    expect(isKind(undefined)).toBe(false)
    expect(isKind({})).toBe(false)
  })
})
