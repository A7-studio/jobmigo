import { describe, expect, it } from 'vitest'
import {
  FIELDS,
  KINDS,
  STATUS_LABEL,
  copyFor,
  datesLabel,
  fromForm,
  progress,
  toForm,
} from '#/lib/profile-view'
import type { Experience, Profile, Skill } from '#/lib/profile-view'

const job = (over: Partial<Experience> = {}): Experience => ({
  id: 'e1',
  status: 'extracted',
  company: 'Northwind',
  role: 'Engineer',
  start: '2021-03',
  end: null,
  isCurrent: true,
  bullets: ['Built the app', 'Cut load time'],
  ...over,
})
const skill = (over: Partial<Skill> = {}): Skill => ({
  id: 's1',
  status: 'extracted',
  name: 'Flutter',
  ...over,
})
const profile = (over: Partial<Profile> = {}): Profile => ({
  id: 'p',
  cvId: 'c',
  version: 1,
  headline: null,
  summary: null,
  experiences: [],
  skills: [],
  achievements: [],
  projects: [],
  education: [],
  ...over,
})

describe('toForm and fromForm', () => {
  it('round-trips an experience, turning bullets into lines and back', () => {
    const values = toForm('experience', job())
    expect(values.bullets).toBe('Built the app\nCut load time')
    expect(values.isCurrent).toBe(true)
    expect(values.end).toBe('')
    const result = fromForm('experience', values, null)
    expect(result).toEqual({
      ok: true,
      body: {
        role: 'Engineer',
        company: 'Northwind',
        start: '2021-03',
        end: null,
        isCurrent: true,
        bullets: ['Built the app', 'Cut load time'],
      },
    })
  })

  it('sends only the fields that changed on an edit, and nothing when none did', () => {
    const original = job()
    const same = toForm('experience', original)
    expect(fromForm('experience', same, original)).toEqual({
      ok: true,
      body: {},
    })
    const changed = { ...same, role: '  Principal Engineer  ', bullets: 'One' }
    expect(fromForm('experience', changed, original)).toEqual({
      ok: true,
      body: { role: 'Principal Engineer', bullets: ['One'] },
    })
  })

  it('turns an emptied optional field into null and trims text', () => {
    const original = job({ end: '2023' })
    const values = { ...toForm('experience', original), end: '   ' }
    expect(fromForm('experience', values, original)).toEqual({
      ok: true,
      body: { end: null },
    })
  })

  it('refuses missing required fields, long text, bad dates and too many points', () => {
    const base = toForm('experience', job())
    const cases: [Record<string, string | boolean>, string][] = [
      [{ ...base, role: '   ' }, 'role'],
      [{ ...base, company: 'x'.repeat(201) }, 'company'],
      [{ ...base, start: 'March 2021' }, 'start'],
      [{ ...base, end: '2021-13' }, 'end'],
      [{ ...base, bullets: Array(21).fill('a').join('\n') }, 'bullets'],
      [{ ...base, bullets: 'x'.repeat(501) }, 'bullets'],
    ]
    for (const [values, key] of cases) {
      const result = fromForm('experience', values, null)
      expect(result.ok).toBe(false)
      if (!result.ok) expect(Object.keys(result.errors)).toContain(key)
    }
  })

  it('has a field spec and a form for every kind, with required fields marked', () => {
    for (const kind of KINDS) {
      expect(FIELDS[kind].length).toBeGreaterThan(0)
      expect(Object.keys(toForm(kind, null))).toEqual(
        FIELDS[kind].map((field) => field.key),
      )
    }
    expect(fromForm('skill', { name: '' }, null)).toMatchObject({ ok: false })
    expect(fromForm('skill', { name: ' Dart ' }, null)).toEqual({
      ok: true,
      body: { name: 'Dart' },
    })
  })

  it('treats a blank related role on an achievement as no link', () => {
    expect(
      fromForm('achievement', { text: 'Shipped', experienceId: '' }, null),
    ).toEqual({ ok: true, body: { text: 'Shipped', experienceId: null } })
  })
})

describe('whitespace is collapsed the way the engine does it (F-100)', () => {
  it('counts the collapsed length and sends the collapsed text', () => {
    const base = toForm('experience', job())
    const spaced = 'a   b\t\tc'
    expect(
      fromForm('experience', { ...base, role: spaced }, null),
    ).toMatchObject({ ok: true, body: { role: 'a b c' } })
    // 60 words separated by double spaces: 238 raw characters, 179 once collapsed
    const long = Array(60).fill('ab').join('  ')
    expect(long.length).toBeGreaterThan(200)
    expect(fromForm('experience', { ...base, role: long }, null)).toMatchObject(
      {
        ok: true,
      },
    )
    expect(
      fromForm('experience', { ...base, role: 'x'.repeat(201) }, null),
    ).toMatchObject({ ok: false })
  })
})

describe('copyFor', () => {
  it('gives every code calm copy that shows no code or raw wording', () => {
    for (const code of [
      'validation_failed',
      'already_exists',
      'limit_reached',
      'not_found',
      'unauthorized',
      'engine_unavailable',
      'network',
      'unexpected',
      'something_new',
    ]) {
      const copy = copyFor(code)
      expect(copy.title.length).toBeGreaterThan(5)
      expect(copy.body.length).toBeGreaterThan(10)
      expect(copy.title + copy.body).not.toMatch(/[a-z]+_[a-z_]+/)
    }
  })
})

describe('display helpers', () => {
  it('words the three statuses so none relies on colour', () => {
    expect(STATUS_LABEL).toEqual({
      extracted: 'Unconfirmed',
      confirmed: 'Confirmed',
      edited: 'Edited by you',
    })
  })

  it('words date ranges', () => {
    expect(datesLabel('2021-03', null, true)).toBe('2021-03 to now')
    expect(datesLabel('2018', '2021', false)).toBe('2018 to 2021')
    expect(datesLabel('2018', null, false)).toBe('from 2018')
    expect(datesLabel(null, '2021', false)).toBe('until 2021')
    expect(datesLabel(null, null, false)).toBe('')
  })

  it('counts confirmed and edited facts as reviewed', () => {
    const p = profile({
      experiences: [job({ status: 'confirmed' }), job({ id: 'e2' })],
      skills: [skill({ status: 'edited' }), skill({ id: 's2' })],
    })
    expect(progress(p)).toEqual({
      reviewed: 2,
      total: 4,
      unconfirmed: 2,
      text: '2 of 4 reviewed',
    })
    expect(progress(profile()).text).toBe('Nothing to review yet')
    expect(
      progress(profile({ skills: [skill({ status: 'confirmed' })] })).text,
    ).toBe('All reviewed')
  })
})
