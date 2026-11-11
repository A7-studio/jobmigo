/** The three kinds of opportunity a job or a track can be. */
export const OPPORTUNITY_KINDS = ['job', 'gig', 'ai_training'] as const
export type OpportunityKind = (typeof OPPORTUNITY_KINDS)[number]

const LABELS: Record<OpportunityKind, string> = {
  job: 'Job',
  gig: 'Freelance gig',
  ai_training: 'AI training role',
}

/** The kit document each kind gets, for the application kit to use later. */
const DOCUMENTS: Record<OpportunityKind, 'cover letter' | 'proposal'> = {
  job: 'cover letter',
  gig: 'proposal',
  ai_training: 'proposal',
}

export const kindLabel = (kind: OpportunityKind): string => LABELS[kind]
export const kindDocument = (kind: OpportunityKind) => DOCUMENTS[kind]

/** True for a word the engine accepts; anything else is not a kind. */
export const isKind = (value: unknown): value is OpportunityKind =>
  typeof value === 'string' &&
  (OPPORTUNITY_KINDS as readonly string[]).includes(value)
