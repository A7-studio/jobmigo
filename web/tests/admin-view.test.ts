import { describe, expect, it } from 'vitest'
import {
  tokens,
  trouble,
  usd,
  windowLabel,
  workflowName,
} from '#/lib/admin-view'

describe('usd', () => {
  it('shows cents, fractions of a cent, and unknown', () => {
    expect(usd('12.3456')).toBe('$12.35')
    expect(usd('0.0042')).toBe('$0.0042')
    expect(usd('0')).toBe('$0.00')
    expect(usd(null)).toBe('Unknown')
    expect(usd('nope')).toBe('Unknown')
  })
})

describe('tokens', () => {
  it('shortens large counts', () => {
    expect(tokens(950)).toBe('950')
    expect(tokens(1500)).toBe('1.5k')
    expect(tokens(25_000)).toBe('25k')
    expect(tokens(2_500_000)).toBe('2.5M')
  })
})

describe('trouble', () => {
  it('is the share of calls without a usable answer', () => {
    expect(trouble(10, 1, 1)).toBe(20)
    expect(trouble(0, 0, 0)).toBeNull()
  })
})

describe('names', () => {
  it('words workflows and windows', () => {
    expect(workflowName('screen')).toBe('Screening a job')
    expect(workflowName('mystery')).toBe('mystery')
    expect(windowLabel(1)).toBe('1 day')
    expect(windowLabel(30)).toBe('30 days')
  })
})
