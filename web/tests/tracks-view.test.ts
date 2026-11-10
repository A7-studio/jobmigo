import { describe, expect, it } from 'vitest'
import {
  checkName,
  emphasisCount,
  isEmphasised,
  trackCopy,
} from '#/lib/tracks-view'
import type { Track } from '#/lib/tracks-view'

const track: Track = {
  id: 't1',
  name: 'Mobile',
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
