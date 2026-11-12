/** Pure rules for tracking a job: stage words, outcome words and follow-up dates. */

import type { Job, Outcome, Stage } from './jobs-api'

export const STAGES: readonly Stage[] = [
  'saved',
  'preparing',
  'applied',
  'interviewing',
  'offer',
  'closed',
]
export const OUTCOMES: readonly Outcome[] = [
  'no_response',
  'rejected',
  'interview',
  'offer',
]

const STAGE_LABELS: Record<Stage, string> = {
  saved: 'Saved',
  preparing: 'Preparing',
  applied: 'Applied',
  interviewing: 'Interviewing',
  offer: 'Offer',
  closed: 'Closed',
}
const OUTCOME_LABELS: Record<Outcome, string> = {
  no_response: 'No response',
  rejected: 'Rejected',
  interview: 'Got an interview',
  offer: 'Got an offer',
}

export const stageLabel = (stage: Stage): string => STAGE_LABELS[stage]
export const outcomeLabel = (outcome: Outcome): string =>
  OUTCOME_LABELS[outcome]

/** How many jobs sit in each stage. */
export function countByStage(jobs: readonly Job[]): Record<Stage, number> {
  const counts = Object.fromEntries(STAGES.map((s) => [s, 0])) as Record<
    Stage,
    number
  >
  for (const job of jobs) counts[job.stage] += 1
  return counts
}

const DAY = 24 * 60 * 60 * 1000

/** A YYYY-MM-DD day as a local date at midnight, or null when it is not a real day. */
function dayOf(value: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!m) return null
  const date = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return date.getFullYear() === Number(m[1]) &&
    date.getMonth() === Number(m[2]) - 1 &&
    date.getDate() === Number(m[3])
    ? date
    : null
}

const startOfDay = (d: Date) =>
  new Date(d.getFullYear(), d.getMonth(), d.getDate())

/** Whole days from `today` to the follow-up day: negative when it has passed. */
export function daysUntil(followUpOn: string, today: Date): number | null {
  const day = dayOf(followUpOn)
  if (!day) return null
  return Math.round((day.getTime() - startOfDay(today).getTime()) / DAY)
}

export type FollowUp = { text: string; due: boolean }

/**
 * What to say about a follow-up day. Once a job is closed, or has an offer, there is
 * nothing left to follow up, so nothing is said.
 */
export function followUpNote(
  job: Pick<Job, 'followUpOn' | 'stage'>,
  today: Date = new Date(),
): FollowUp | null {
  if (!job.followUpOn || job.stage === 'closed' || job.stage === 'offer') {
    return null
  }
  const days = daysUntil(job.followUpOn, today)
  if (days === null) return null
  if (days < 0) {
    return {
      text: `Follow-up was due ${-days} ${days === -1 ? 'day' : 'days'} ago`,
      due: true,
    }
  }
  if (days === 0) return { text: 'Follow up today', due: true }
  if (days === 1) return { text: 'Follow up tomorrow', due: false }
  return { text: `Follow up in ${days} days`, due: false }
}

/** "Applied today", "Applied yesterday", "Applied 3 days ago". */
export function appliedNote(
  appliedAt: string | null,
  today: Date = new Date(),
): string | null {
  if (!appliedAt) return null
  const then = new Date(appliedAt)
  if (Number.isNaN(then.getTime())) return null
  const days = Math.round(
    (startOfDay(today).getTime() - startOfDay(then).getTime()) / DAY,
  )
  if (days <= 0) return 'Applied today'
  if (days === 1) return 'Applied yesterday'
  return `Applied ${days} days ago`
}

/** Calm wording for a tracking error code; never shows a code. */
export function trackingCopy(code: string): { title: string; body: string } {
  switch (code) {
    case 'validation_failed':
      return {
        title: 'That was not accepted',
        body: 'Check the date and the notes (up to 4,000 characters). Nothing was changed.',
      }
    case 'not_found':
      return {
        title: 'That job is no longer there',
        body: 'It may have been removed in another tab. Reload the page.',
      }
    case 'network':
      return {
        title: 'We could not reach Jobmigo',
        body: 'Check your connection and try again. Nothing changed.',
      }
    default:
      return {
        title: 'Something went wrong',
        body: 'Try again in a moment. Nothing changed.',
      }
  }
}

export const MAX_NOTES = 4000
