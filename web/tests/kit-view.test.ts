import { describe, expect, it } from 'vitest'
import {
  blockLimit,
  blocksOf,
  checkQuestions,
  checkSummary,
  docLabel,
  docsInOrder,
  factLine,
  factLines,
  flagWords,
  kitCopy,
  needsYou,
  preview,
  versionLabel,
} from '#/lib/kit-view'
import type { KitBlock, KitContent, KitVersion } from '#/lib/jobs-api'

const block = (text: string, flags: KitBlock['flags'] = []): KitBlock => ({
  text,
  sources: [],
  flags,
  numbers: flags.includes('unsupported_number') ? ['12'] : [],
})

const CV: KitContent = {
  docType: 'cv',
  summary: block('Lead.'),
  entries: [
    {
      heading: 'Lead at BeatBnk',
      kind: 'experience',
      source: { label: 'E1', kind: 'experience', id: 'a' },
      bullets: [block('One.'), block('Led 12.', ['unsupported_number'])],
    },
    {
      heading: 'Engineer at Alvin',
      kind: 'experience',
      source: { label: 'E2', kind: 'experience', id: 'b' },
      bullets: [block('Two.', ['no_source'])],
    },
  ],
  skills: [],
}

const version = (
  docType: KitVersion['docType'],
  over: Partial<KitVersion> = {},
): KitVersion => ({
  id: docType,
  jobId: 'j',
  trackId: 't',
  trackName: 'Mobile',
  docType,
  version: 1,
  profileVersion: 1,
  stale: false,
  content: CV,
  factCheck: { blocks: 4, flagged: 2, flags: [], omitted: 0, edited: [] },
  createdAt: '2026-11-11T00:00:00Z',
  ...over,
})

describe('words', () => {
  it('names each document and keeps reading order', () => {
    expect(docLabel('proposal')).toBe('Proposal')
    expect(
      docsInOrder([version('answers'), version('letter'), version('cv')]).map(
        (v) => v.docType,
      ),
    ).toEqual(['cv', 'letter', 'answers'])
  })

  it('says why a statement was flagged without a code', () => {
    expect(flagWords('unsupported_number', ['12'])).toBe(
      'The number 12 is not in the facts it cites.',
    )
    expect(flagWords('unsupported_number', ['3', '4'])).toContain(
      'numbers 3, 4',
    )
    expect(flagWords('no_source', [])).toContain('confirmed')
    for (const flag of [
      'no_source',
      'unsupported_number',
      'empty',
      'too_long',
      'off_entry',
    ] as const) {
      expect(flagWords(flag, [])).not.toContain('_')
    }
  })

  it('labels a version', () => {
    expect(versionLabel(2, 2)).toBe('Version 2 (latest)')
    expect(versionLabel(1, 2)).toBe('Version 1')
  })
})

describe('blocksOf and needsYou', () => {
  it('walks a CV in reading order with paths and where each sits', () => {
    expect(blocksOf(CV).map((l) => [l.path, l.where, l.canRemove])).toEqual([
      ['summary', 'Summary', false],
      ['entries.1.bullets.1', 'Lead at BeatBnk', true],
      ['entries.1.bullets.2', 'Lead at BeatBnk', true],
      ['entries.2.bullets.1', 'Engineer at Alvin', true],
    ])
  })

  it('lists only what needs the person', () => {
    expect(needsYou(CV).map((l) => l.path)).toEqual([
      'entries.1.bullets.2',
      'entries.2.bullets.1',
    ])
  })

  it('letters and proposals can lose all but the last paragraph; answers cannot be removed', () => {
    const one: KitContent = { docType: 'letter', paragraphs: [block('a')] }
    const two: KitContent = {
      docType: 'proposal',
      paragraphs: [block('a'), block('b')],
    }
    expect(blocksOf(one).map((l) => l.canRemove)).toEqual([false])
    expect(blocksOf(two).map((l) => l.canRemove)).toEqual([true, true])
    const answers: KitContent = {
      docType: 'answers',
      answers: [{ ...block('Yes.'), index: 1, question: 'Why us?' }],
    }
    expect(blocksOf(answers)).toMatchObject([
      { path: 'answers.1', where: 'Why us?', canRemove: false },
    ])
  })
})

describe('checkSummary', () => {
  it('says what traces and what needs you, never a percentage', () => {
    const s = checkSummary(version('cv'))
    expect(s.traced).toBe(
      '2 of 4 statements cite a confirmed fact and keep its numbers.',
    )
    expect(s.needs).toBe('2 need you.')
    expect(s.omitted).toBeNull()
    expect(`${s.traced}${s.needs}`).not.toContain('%')
  })

  it('is calm when nothing is flagged and notes what was left out', () => {
    const s = checkSummary(
      version('cv', {
        factCheck: { blocks: 1, flagged: 0, flags: [], omitted: 2, edited: [] },
      }),
    )
    expect(s.traced).toBe(
      '1 of 1 statement cites a confirmed fact and keeps its numbers.',
    )
    expect(s.needs).toBeNull()
    expect(s.omitted).toContain('2 entries or skills were left out')
  })
})

describe('checkQuestions', () => {
  it('reads one question per line and drops blanks', () => {
    expect(checkQuestions('  Why us?  \n\n  Start   date? \n')).toEqual({
      ok: true,
      questions: ['Why us?', 'Start date?'],
    })
    expect(checkQuestions('   ')).toEqual({ ok: true, questions: [] })
  })

  it('refuses too many or too long', () => {
    expect(checkQuestions('a\nb\nc\nd\ne\nf')).toMatchObject({ ok: false })
    expect(checkQuestions(`ok\n${'x'.repeat(501)}`)).toMatchObject({
      ok: false,
      error: expect.stringContaining('Question 2'),
    })
  })
})

describe('kitCopy', () => {
  it('has calm wording and never shows a code', () => {
    for (const code of [
      'no_confirmed_profile',
      'ai_not_configured',
      'ai_unavailable',
      'ai_output_invalid',
      'wrong_type',
      'validation_failed',
      'invalid_edit',
      'needs_fixing',
      'not_latest',
      'not_found',
      'network',
      'weird_code',
    ]) {
      const copy = kitCopy(code)
      expect(copy.title + copy.body).not.toContain('_')
    }
    expect(kitCopy('not_latest').action).toBe('reload')
    expect(kitCopy('ai_unavailable').action).toBe('retry')
    expect(kitCopy('no_confirmed_profile').action).toBe('profile')
  })
})

describe('factLine', () => {
  const base = { status: 'confirmed' as const }
  it('words each kind of fact', () => {
    expect(
      factLine({
        ...base,
        id: 'a',
        company: 'BeatBnk',
        role: 'Lead',
        start: '2025-01',
        end: null,
        isCurrent: true,
        bullets: [],
      }),
    ).toBe('Lead at BeatBnk (2025-01 to present)')
    expect(
      factLine({
        ...base,
        id: 'b',
        company: 'Alvin',
        role: 'Engineer',
        start: null,
        end: null,
        isCurrent: false,
        bullets: [],
      }),
    ).toBe('Engineer at Alvin')
    expect(
      factLine({
        ...base,
        id: 'c',
        institution: 'Meru',
        qualification: 'BSc',
        start: null,
        end: null,
      }),
    ).toBe('BSc at Meru')
    expect(
      factLine({
        ...base,
        id: 'd',
        institution: 'Meru',
        qualification: null,
        start: null,
        end: null,
      }),
    ).toBe('Meru')
    expect(
      factLine({ ...base, id: 'e', text: 'Won 3 awards', experienceId: null }),
    ).toBe('Won 3 awards')
    expect(factLine({ ...base, id: 'f', name: 'Flutter' })).toBe('Flutter')
  })

  it('maps every fact of a profile by id', () => {
    const lines = factLines({
      id: 'p',
      cvId: 'c',
      version: 1,
      headline: null,
      summary: null,
      experiences: [],
      skills: [{ ...base, id: 's1', name: 'Flutter' }],
      achievements: [],
      projects: [{ ...base, id: 'p1', name: 'Kakitoo', description: null }],
      education: [],
    })
    expect([...lines]).toEqual([
      ['s1', 'Flutter'],
      ['p1', 'Kakitoo'],
    ])
  })
})

describe('blockLimit and preview', () => {
  it('uses the engine limits by place', () => {
    expect(blockLimit('summary')).toBe(600)
    expect(blockLimit('entries.2.bullets.1')).toBe(300)
    expect(blockLimit('paragraphs.3')).toBe(1200)
    expect(blockLimit('answers.1')).toBe(1500)
  })

  it('shortens a statement so a button can name it', () => {
    expect(preview('  Cut   bugs\nby 60%. ')).toBe('Cut bugs by 60%.')
    expect(preview('x'.repeat(60))).toBe(`${'x'.repeat(40)}…`)
    expect(preview('')).toBe('')
  })
})
