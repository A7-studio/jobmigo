/** Pure rules for the CV and letter step: words, ordering, what needs the person. */

import { allFacts } from './profile-view'
import type { Fact, Profile } from './profile-view'
import type {
  KitBlock,
  KitContent,
  KitDocType,
  KitFlag,
  KitVersion,
} from './jobs-api'

const DOC_ORDER: KitDocType[] = ['cv', 'letter', 'proposal', 'answers']

const DOC_LABELS: Record<KitDocType, string> = {
  cv: 'CV',
  letter: 'Cover letter',
  proposal: 'Proposal',
  answers: 'Answers',
}

export const docLabel = (docType: KitDocType): string => DOC_LABELS[docType]

/** The documents of a kit in reading order: CV, letter or proposal, then answers. */
export function docsInOrder(versions: readonly KitVersion[]): KitVersion[] {
  return [...versions].sort(
    (a, b) => DOC_ORDER.indexOf(a.docType) - DOC_ORDER.indexOf(b.docType),
  )
}

/** Why a statement was flagged, in plain words. */
export function flagWords(flag: KitFlag, numbers: readonly string[]): string {
  switch (flag) {
    case 'no_source':
      return 'It is not tied to a fact you confirmed.'
    case 'unsupported_number':
      return numbers.length > 0
        ? `The ${numbers.length === 1 ? 'number' : 'numbers'} ${numbers.join(', ')} ${numbers.length === 1 ? 'is' : 'are'} not in the facts it cites.`
        : 'A number in it is not in the facts it cites.'
    case 'empty':
      return 'It is empty.'
    case 'too_long':
      return 'It is too long.'
    case 'off_entry':
      return 'It leans on a fact from a different job or school.'
  }
}

export type Located = {
  /** The path the engine knows the statement by, for example `entries.1.bullets.2`. */
  path: string
  /** Where it sits, in words. */
  where: string
  block: KitBlock
  /** What a person may do with it. */
  canRemove: boolean
}

/** Every statement of a document, in reading order, with where it sits. */
export function blocksOf(content: KitContent): Located[] {
  switch (content.docType) {
    case 'cv': {
      const out: Located[] = [
        {
          path: 'summary',
          where: 'Summary',
          block: content.summary,
          canRemove: false,
        },
      ]
      content.entries.forEach((entry, e) => {
        entry.bullets.forEach((block, b) => {
          out.push({
            path: `entries.${e + 1}.bullets.${b + 1}`,
            where: entry.heading,
            block,
            canRemove: true,
          })
        })
      })
      return out
    }
    case 'letter':
    case 'proposal':
      return content.paragraphs.map((block, n) => ({
        path: `paragraphs.${n + 1}`,
        where: `Paragraph ${n + 1}`,
        block,
        canRemove: content.paragraphs.length > 1,
      }))
    case 'answers':
      return content.answers.map((block, n) => ({
        path: `answers.${n + 1}`,
        where: block.question,
        block,
        canRemove: false,
      }))
  }
}

/** The statements that need the person, in reading order. */
export const needsYou = (content: KitContent): Located[] =>
  blocksOf(content).filter((l) => l.block.flags.length > 0)

/** The sentence under the document: what traces to a confirmed fact, and what needs you. */
export function checkSummary(version: KitVersion): {
  traced: string
  needs: string | null
  omitted: string | null
} {
  const { blocks, flagged, omitted } = version.factCheck
  const ok = Math.max(blocks - flagged, 0)
  return {
    traced: `${ok} of ${blocks} ${blocks === 1 ? 'statement cites' : 'statements cite'} a confirmed fact and keep${blocks === 1 ? 's' : ''} its numbers.`,
    needs:
      flagged === 0
        ? null
        : `${flagged} ${flagged === 1 ? 'needs' : 'need'} you.`,
    omitted:
      omitted > 0
        ? `${omitted} ${omitted === 1 ? 'entry or skill was' : 'entries or skills were'} left out because your facts do not back them.`
        : null,
  }
}

/** "Version 2 (latest)" or "Version 1". */
export const versionLabel = (version: number, latest: number): string =>
  `Version ${version}${version === latest ? ' (latest)' : ''}`

export type QuestionsResult =
  { ok: true; questions: string[] } | { ok: false; error: string }

export const MAX_QUESTIONS = 5
export const MAX_QUESTION_CHARS = 500

/** One question per line. Blank lines are dropped. */
export function checkQuestions(raw: string): QuestionsResult {
  const questions = raw
    .split('\n')
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter((line) => line !== '')
  if (questions.length > MAX_QUESTIONS) {
    return { ok: false, error: `Use ${MAX_QUESTIONS} questions or fewer.` }
  }
  const long = questions.findIndex((q) => q.length > MAX_QUESTION_CHARS)
  if (long !== -1) {
    return {
      ok: false,
      error: `Question ${long + 1} is too long. Keep each to ${MAX_QUESTION_CHARS} characters.`,
    }
  }
  return { ok: true, questions }
}

type Copy = {
  title: string
  body: string
  action: 'retry' | 'profile' | 'reload' | 'none'
}

/** Calm wording for a writing or editing error code; never shows a code or a raw message. */
export function kitCopy(code: string): Copy {
  switch (code) {
    case 'no_confirmed_profile':
      return {
        title: 'Confirm some of your profile first',
        body: 'The CV and letter only use facts you have confirmed. Review your profile, then come back.',
        action: 'profile',
      }
    case 'ai_not_configured':
      return {
        title: 'Writing is not switched on',
        body: 'No model is set up on this machine yet. Nothing was saved.',
        action: 'none',
      }
    case 'ai_unavailable':
    case 'ai_output_invalid':
      return {
        title: 'Writing did not finish',
        body: 'The model did not give a usable answer. Nothing was saved. Try again.',
        action: 'retry',
      }
    case 'wrong_type':
      return {
        title: 'That track is for a different kind of work',
        body: 'Choose a track of this job’s kind.',
        action: 'none',
      }
    case 'validation_failed':
      return {
        title: 'That was not accepted',
        body: 'Check the questions and try again. Nothing was saved.',
        action: 'none',
      }
    case 'invalid_edit':
      return {
        title: 'That change was not accepted',
        body: 'Check the text and try again. Nothing was changed.',
        action: 'none',
      }
    case 'needs_fixing':
      return {
        title: 'Some statements still need you',
        body: 'Edit or remove what is flagged above, then try again. If nothing is flagged there, a fact it cites has changed in your profile, so write the kit again.',
        action: 'none',
      }
    case 'not_latest':
      return {
        title: 'There is a newer version',
        body: 'Another change was saved first. Reload to see it.',
        action: 'reload',
      }
    case 'not_found':
      return {
        title: 'That is no longer there',
        body: 'It may have been removed in another tab. Reload the page.',
        action: 'reload',
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

/** One plain line for a profile fact, as the person would recognise it. */
export function factLine(fact: Fact): string {
  if ('role' in fact) {
    const span = [fact.start, fact.isCurrent ? 'present' : fact.end]
      .filter((v): v is string => Boolean(v))
      .join(' to ')
    return `${fact.role} at ${fact.company}${span ? ` (${span})` : ''}`
  }
  if ('institution' in fact) {
    return fact.qualification
      ? `${fact.qualification} at ${fact.institution}`
      : fact.institution
  }
  if ('text' in fact) return fact.text
  return fact.name
}

/** Every fact of a profile by id, as one line: what a statement's sources point to. */
export function factLines(profile: Profile): Map<string, string> {
  return new Map(allFacts(profile).map(({ fact }) => [fact.id, factLine(fact)]))
}

/** How long a statement may be, by where it sits. These are the engine's own limits. */
export function blockLimit(path: string): number {
  if (path === 'summary') return 600
  if (path.startsWith('paragraphs.')) return 1200
  if (path.startsWith('answers.')) return 1500
  return 300
}

/** The start of a statement, for a button's name, so each one is told apart. */
export function preview(text: string, length = 40): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length > length ? `${flat.slice(0, length).trimEnd()}…` : flat
}
