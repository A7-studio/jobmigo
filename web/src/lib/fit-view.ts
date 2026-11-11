/** Pure rules for the Fit step: plain words for each state, and which result to show. */

import type {
  Evaluation,
  EvaluatedRequirement,
  EvaluationChecks,
  Importance,
  RequirementStatus,
} from './jobs-api'

const STATUS_WORDS: Record<RequirementStatus, string> = {
  met: 'Evidence found',
  partial: 'Partly covered',
  gap: 'Gap',
  unknown: 'Not shown in your profile',
}

export const statusLabel = (status: RequirementStatus): string =>
  STATUS_WORDS[status]

/** Importance is our guess, so it is worded as a guess and never as "must". */
export const importanceLabel = (importance: Importance): string =>
  importance === 'important' ? 'Looks important' : 'Looks nice to have'

export type CheckRow = {
  label: string
  value: string
  tone: 'good' | 'warn' | 'neutral'
  note: string | null
}

const money = (amount: number, currency: string | null) =>
  `${Math.round(amount).toLocaleString('en-US')}${currency ? ` ${currency}` : ''}`

/** The three practical checks as rows, in a fixed order. */
export function checkRows(checks: EvaluationChecks): CheckRow[] {
  const { salary, workMode, region } = checks
  const salaryRow: CheckRow =
    salary.status === 'meets'
      ? {
          label: 'Pay',
          value: 'Meets your floor',
          tone: 'good',
          note:
            salary.postingMonthly !== null
              ? `About ${money(salary.postingMonthly, salary.currency)} a month in the posting.`
              : null,
        }
      : salary.status === 'below'
        ? {
            label: 'Pay',
            value: 'Below your floor',
            tone: 'warn',
            note:
              salary.postingMonthly !== null && salary.floorMonthly !== null
                ? `The posting is about ${money(salary.postingMonthly, salary.currency)} a month; your floor is ${money(salary.floorMonthly, salary.currency)}.`
                : null,
          }
        : {
            label: 'Pay',
            value: 'Not stated, or cannot be compared',
            tone: 'neutral',
            note: null,
          }
  const modes = {
    remote: 'remote',
    hybrid: 'hybrid',
    onsite: 'on site',
  } as const
  const workRow: CheckRow =
    workMode.status === 'matches'
      ? {
          label: 'Work mode',
          value: 'Matches your track',
          tone: 'good',
          note: workMode.posting
            ? `The posting says ${modes[workMode.posting]}.`
            : null,
        }
      : workMode.status === 'differs'
        ? {
            label: 'Work mode',
            value: 'Differs from your track',
            tone: 'warn',
            note: workMode.posting
              ? `The posting says ${modes[workMode.posting]}.`
              : null,
          }
        : {
            label: 'Work mode',
            value: 'Not clear from the posting',
            tone: 'neutral',
            note: null,
          }
  const regionRow: CheckRow =
    region.status === 'compatible'
      ? {
          label: 'Region',
          value: 'Compatible',
          tone: 'good',
          note: region.region,
        }
      : region.status === 'mismatch'
        ? {
            label: 'Region',
            value: 'May not hire where you are',
            tone: 'warn',
            note: region.region,
          }
        : region.status === 'unclear'
          ? {
              label: 'Region',
              value: 'Unclear',
              tone: 'neutral',
              note: region.region,
            }
          : {
              label: 'Region',
              value: 'No region limit found',
              tone: 'neutral',
              note: null,
            }
  return [salaryRow, workRow, regionRow]
}

/** Requirements worth reading first: gaps, then unknowns, then partial, then met. */
const ORDER: Record<RequirementStatus, number> = {
  gap: 0,
  unknown: 1,
  partial: 2,
  met: 3,
}

export function sortRequirements(
  reqs: readonly EvaluatedRequirement[],
): EvaluatedRequirement[] {
  return reqs
    .map((r, at) => ({ r, at }))
    .sort(
      (a, b) =>
        ORDER[a.r.status] - ORDER[b.r.status] ||
        (a.r.importance === b.r.importance
          ? 0
          : a.r.importance === 'important'
            ? -1
            : 1) ||
        a.at - b.at,
    )
    .map((x) => x.r)
}

/** The kept result for one track, or null. */
export const evaluationFor = (
  evaluations: readonly Evaluation[],
  trackId: string,
): Evaluation | null => evaluations.find((e) => e.trackId === trackId) ?? null

/** The track to show first: the one the caller chose if it still exists, else the first. */
export function pickTrack(
  tracks: readonly { id: string }[],
  chosen: string | null,
): string | null {
  if (chosen && tracks.some((t) => t.id === chosen)) return chosen
  return tracks[0]?.id ?? null
}

type Copy = {
  title: string
  body: string
  action: 'retry' | 'profile' | 'none'
}

/** Calm wording for an evaluation error code; never shows a code or a raw message. */
export function fitCopy(code: string): Copy {
  switch (code) {
    case 'no_confirmed_profile':
      return {
        title: 'Confirm some of your profile first',
        body: 'The fit check only uses facts you have confirmed. Review your profile, then come back.',
        action: 'profile',
      }
    case 'no_requirements':
      return {
        title: 'We could not find requirements in this posting',
        body: 'The text may be too short or not a job description. Nothing was saved.',
        action: 'none',
      }
    case 'ai_not_configured':
      return {
        title: 'The fit check is not switched on',
        body: 'No model is set up on this machine yet. Nothing was saved.',
        action: 'none',
      }
    case 'ai_unavailable':
    case 'ai_output_invalid':
      return {
        title: 'The fit check did not finish',
        body: 'The model did not give a usable answer. Nothing was saved. Try again.',
        action: 'retry',
      }
    case 'not_found':
      return {
        title: 'That track or job is no longer there',
        body: 'It may have been removed in another tab. Reload the page.',
        action: 'none',
      }
    case 'network':
      return {
        title: 'We could not reach Jobmigo',
        body: 'Check your connection and try again. Nothing changed.',
        action: 'retry',
      }
    default:
      return {
        title: 'Something went wrong',
        body: 'Try again in a moment. Nothing was saved.',
        action: 'retry',
      }
  }
}
