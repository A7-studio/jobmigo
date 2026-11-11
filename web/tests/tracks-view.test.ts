import { describe, expect, it } from 'vitest'
import {
  checkName,
  fromPrefsForm,
  toPrefsForm,
  emphasisCount,
  isEmphasised,
  trackCopy,
} from '#/lib/tracks-view'
import type { Preferences, Track } from '#/lib/tracks-view'

const EMPTY: Preferences = {
  targetRoles: [],
  salaryFloor: null,
  currency: null,
  workModes: [],
  locations: [],
  eligibility: null,
  criteria: [],
  dealbreakers: [],
  doNotApply: [],
}

const track: Track = {
  preferences: EMPTY,
  id: 't1',
  name: 'Mobile',
  kind: 'job',
  variantVersion: 2,
  emphasis: [
    { kind: 'skill', itemId: 's1' },
    { kind: 'project', itemId: 'p1' },
  ],
}

describe('checkName', () => {
  it('collapses whitespace and accepts a good name', () => {
    expect(checkName('  Flutter   and\tmobile ', [])).toEqual({
      ok: true,
      name: 'Flutter and mobile',
    })
  })
  it('refuses empty, over-long and duplicate names with a reason', () => {
    expect(checkName('   ', [])).toMatchObject({ ok: false })
    expect(checkName('x'.repeat(61), [])).toMatchObject({ ok: false })
    expect(checkName('x'.repeat(60), [])).toMatchObject({ ok: true })
    expect(checkName('mobile', ['Mobile'])).toMatchObject({
      ok: false,
      error: 'You already have a track with that name.',
    })
  })
  it('counts the collapsed length like the engine', () => {
    const spaced = Array(18).fill('ab').join('  ') // 70 raw, 53 collapsed
    expect(spaced.length).toBeGreaterThan(60)
    expect(checkName(spaced, [])).toMatchObject({ ok: true })
  })
})

describe('emphasis helpers', () => {
  it('finds an emphasised fact by kind and id', () => {
    expect(isEmphasised(track, 'skill', 's1')).toBe(true)
    expect(isEmphasised(track, 'project', 's1')).toBe(false)
  })
  it('counts only facts the screen still shows', () => {
    expect(emphasisCount(track, new Set(['s1']))).toBe(1)
    expect(emphasisCount(track, new Set())).toBe(0)
  })
})

describe('trackCopy', () => {
  it('has calm copy for every code and never shows a code', () => {
    for (const code of [
      'validation_failed',
      'already_exists',
      'limit_reached',
      'not_confirmed',
      'not_found',
      'network',
      'unexpected',
      'internal_error',
    ]) {
      const { title, body } = trackCopy(code)
      expect(title.length).toBeGreaterThan(0)
      expect(`${title} ${body}`).not.toMatch(/_|\b[45]\d\d\b/)
    }
  })
})

describe('preferences form', () => {
  it('round-trips stored values into a form and back to no change', () => {
    const stored: Preferences = {
      ...EMPTY,
      targetRoles: ['Flutter engineer'],
      salaryFloor: 65000,
      currency: 'USD',
      workModes: ['remote'],
      criteria: [
        { label: 'Flutter', weight: 'must' },
        { label: 'Fintech', weight: 'nice' },
      ],
    }
    const form = toPrefsForm(stored)
    expect(form.salaryFloor).toBe('65000')
    expect(form.must).toBe('Flutter')
    expect(fromPrefsForm(form, stored)).toEqual({ ok: true, body: {} })
  })

  it('sends only what changed, with whitespace collapsed and blank lines dropped', () => {
    const form = {
      ...toPrefsForm(EMPTY),
      targetRoles: '  Flutter   engineer \n\n Mobile lead ',
      salaryFloor: '65,000',
      currency: ' usd ',
      workModes: ['hybrid', 'remote'] as ('hybrid' | 'remote')[],
      important: 'Remote friendly',
    }
    expect(fromPrefsForm(form, EMPTY)).toEqual({
      ok: true,
      body: {
        targetRoles: ['Flutter engineer', 'Mobile lead'],
        salaryFloor: 65000,
        currency: 'USD',
        workModes: ['remote', 'hybrid'],
        criteria: [{ label: 'Remote friendly', weight: 'important' }],
      },
    })
  })

  it('clears a field when it is emptied', () => {
    const stored: Preferences = { ...EMPTY, salaryFloor: 5, currency: 'USD' }
    const form = { ...toPrefsForm(stored), salaryFloor: '', currency: '' }
    expect(fromPrefsForm(form, stored)).toEqual({
      ok: true,
      body: { salaryFloor: null, currency: null },
    })
  })

  it('says what is wrong beside each field', () => {
    const base = toPrefsForm(EMPTY)
    const bad = (patch: Partial<typeof base>) => {
      const result = fromPrefsForm({ ...base, ...patch }, EMPTY)
      return result.ok ? {} : result.errors
    }
    expect(
      bad({
        targetRoles: Array(11)
          .fill('a')
          .map((x, i) => x + i)
          .join('\n'),
      }),
    ).toHaveProperty('targetRoles')
    expect(bad({ locations: 'Nairobi\nnairobi' })).toHaveProperty('locations')
    expect(bad({ dealbreakers: 'x'.repeat(121) })).toHaveProperty(
      'dealbreakers',
    )
    expect(bad({ doNotApply: 'x'.repeat(81) })).toHaveProperty('doNotApply')
    expect(bad({ eligibility: 'x'.repeat(501) })).toHaveProperty('eligibility')
    expect(bad({ salaryFloor: '12abc', currency: 'USD' })).toHaveProperty(
      'salaryFloor',
    )
    expect(bad({ salaryFloor: '10000001', currency: 'USD' })).toHaveProperty(
      'salaryFloor',
    )
    expect(bad({ salaryFloor: '100' })).toHaveProperty('currency')
    expect(bad({ currency: 'US' })).toHaveProperty('currency')
    expect(bad({ must: 'Same', nice: 'same' })).toHaveProperty('must')
  })

  it('counts the collapsed length like the engine', () => {
    const spaced = Array(30).fill('ab').join('  ') // 118 raw, 89 collapsed
    expect(spaced.length).toBeGreaterThan(80)
    const ok = Array(25).fill('ab').join('  ') // 98 raw, 74 collapsed
    expect(ok.length).toBeGreaterThan(80)
    const tooLong = { ...toPrefsForm(EMPTY), targetRoles: spaced }
    expect(fromPrefsForm(tooLong, EMPTY)).toMatchObject({ ok: false })
    const form = { ...toPrefsForm(EMPTY), targetRoles: ok }
    expect(fromPrefsForm(form, EMPTY)).toMatchObject({ ok: true })
  })
})
