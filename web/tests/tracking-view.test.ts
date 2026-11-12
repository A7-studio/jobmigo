import { describe, expect, it } from 'vitest'
import {
  appliedNote,
  countByStage,
  daysUntil,
  followUpNote,
  outcomeLabel,
  stageLabel,
  trackingCopy,
} from '#/lib/tracking-view'
import type { Job } from '#/lib/jobs-api'

const TODAY = new Date(2026, 10, 12, 15, 30) // 12 Nov 2026, mid-afternoon

describe('words', () => {
  it('names every stage and outcome in plain language', () => {
    expect(stageLabel('interviewing')).toBe('Interviewing')
    expect(outcomeLabel('no_response')).toBe('No response')
    expect(outcomeLabel('interview')).toBe('Got an interview')
  })

  it('never shows a code in an error', () => {
    for (const code of ['validation_failed', 'not_found', 'network', 'x_y']) {
      const copy = trackingCopy(code)
      expect(copy.title + copy.body).not.toContain('_')
    }
  })
})

describe('daysUntil', () => {
  it('counts whole calendar days, ignoring the time of day', () => {
    expect(daysUntil('2026-11-12', TODAY)).toBe(0)
    expect(daysUntil('2026-11-13', TODAY)).toBe(1)
    expect(daysUntil('2026-11-09', TODAY)).toBe(-3)
    expect(daysUntil('2026-12-01', TODAY)).toBe(19)
  })

  it('refuses a day that is not real', () => {
    for (const bad of [
      '',
      'tomorrow',
      '2026-02-30',
      '2026-13-01',
      '2026-1-1',
    ]) {
      expect(daysUntil(bad, TODAY)).toBeNull()
    }
  })
})

describe('followUpNote', () => {
  const job = (followUpOn: string | null, stage: Job['stage'] = 'applied') => ({
    followUpOn,
    stage,
  })

  it('says when a follow-up is due, today, soon or later', () => {
    expect(followUpNote(job('2026-11-09'), TODAY)).toEqual({
      text: 'Follow-up was due 3 days ago',
      due: true,
    })
    expect(followUpNote(job('2026-11-11'), TODAY)?.text).toBe(
      'Follow-up was due 1 day ago',
    )
    expect(followUpNote(job('2026-11-12'), TODAY)).toEqual({
      text: 'Follow up today',
      due: true,
    })
    expect(followUpNote(job('2026-11-13'), TODAY)).toEqual({
      text: 'Follow up tomorrow',
      due: false,
    })
    expect(followUpNote(job('2026-11-20'), TODAY)).toEqual({
      text: 'Follow up in 8 days',
      due: false,
    })
  })

  it('says nothing without a date, with a bad date, or once nothing is left to chase', () => {
    expect(followUpNote(job(null), TODAY)).toBeNull()
    expect(followUpNote(job('soon'), TODAY)).toBeNull()
    expect(followUpNote(job('2026-11-01', 'closed'), TODAY)).toBeNull()
    expect(followUpNote(job('2026-11-01', 'offer'), TODAY)).toBeNull()
  })
})

describe('appliedNote', () => {
  it('says how long ago', () => {
    expect(appliedNote(null, TODAY)).toBeNull()
    expect(appliedNote('not a date', TODAY)).toBeNull()
    expect(appliedNote(new Date(2026, 10, 12, 1).toISOString(), TODAY)).toBe(
      'Applied today',
    )
    expect(appliedNote(new Date(2026, 10, 11, 23).toISOString(), TODAY)).toBe(
      'Applied yesterday',
    )
    expect(appliedNote(new Date(2026, 10, 9, 9).toISOString(), TODAY)).toBe(
      'Applied 3 days ago',
    )
  })
})

describe('countByStage', () => {
  it('counts each stage, with zeros', () => {
    const jobs = [
      { stage: 'saved' },
      { stage: 'saved' },
      { stage: 'applied' },
    ] as Job[]
    expect(countByStage(jobs)).toEqual({
      saved: 2,
      preparing: 0,
      applied: 1,
      interviewing: 0,
      offer: 0,
      closed: 0,
    })
  })
})
