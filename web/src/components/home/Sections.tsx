import { FeatureSection, Pill, PreviewCard } from './Feature'

const JOBS = [
  {
    initial: 'L',
    title: 'Senior Flutter Engineer',
    meta: 'Lumen Health · Verified live 2h ago',
    tone: 'good',
    label: 'Live',
  },
  {
    initial: 'T',
    title: 'AI Code Evaluator',
    meta: 'Tidewater Labs · 2 listings merged into 1',
    tone: 'info',
    label: 'Merged',
  },
  {
    initial: 'N',
    title: 'Product Engineer, LLM Tools',
    meta: 'Northwind · Reposted 3 times in 60 days',
    tone: 'warn',
    label: 'Check first',
  },
  {
    initial: 'H',
    title: 'Senior Mobile Engineer',
    meta: 'Harbor · Posting removed 4 Nov',
    tone: 'neutral',
    label: 'Closed',
  },
] as const

export function Discover() {
  return (
    <FeatureSection
      eyebrow="Discover and verify"
      title="Only jobs that are really open."
      body="Jobmigo will read public career pages and job feeds, check each posting is still live, and merge duplicates so you see every role once."
      points={[
        'Live checks on every posting',
        'Duplicates merged, closed roles removed',
        'Ghost-job and repost warnings',
      ]}
    >
      <PreviewCard title="Jobs, checked">
        <ul className="flex flex-col divide-y divide-border">
          {JOBS.map((job) => (
            <li key={job.title} className="flex items-center gap-3 py-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent-soft font-extrabold text-accent-soft-ink">
                {job.initial}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-bold">{job.title}</span>
                <span className="block text-xs text-muted">{job.meta}</span>
              </span>
              <Pill tone={job.tone}>{job.label}</Pill>
            </li>
          ))}
        </ul>
      </PreviewCard>
    </FeatureSection>
  )
}

export function Evaluate() {
  const rows = [
    {
      mark: '✓ Met',
      tone: 'good',
      req: 'Offline-first sync',
      evidence: 'Local-first sync layer at Meridian (your CV)',
    },
    {
      mark: '✓ Met',
      tone: 'good',
      req: 'Riverpod or Bloc',
      evidence: 'Provider to Riverpod migration (your CV)',
    },
    {
      mark: '✕ Gap',
      tone: 'bad',
      req: 'Native iOS (Swift)',
      evidence: 'Nothing in your profile yet',
    },
  ] as const
  return (
    <FeatureSection
      flip
      eyebrow="Evaluate"
      title="Honest fit, with receipts."
      body="See exactly why a job suits you or not. Each requirement is matched to evidence from your own CV, and gaps are named plainly."
      points={[
        'Fit bands, never a made-up percentage',
        'Salary, location and eligibility checked',
        'Your dealbreakers applied before anything else',
      ]}
    >
      <PreviewCard
        title="Senior Flutter Engineer"
        note="No magic percentage. Every verdict points to a line in your CV or the posting."
      >
        <div className="flex items-center gap-2">
          <Pill tone="good">Strong fit</Pill>
          <span className="text-sm text-muted">
            6 of 7 must-haves evidenced
          </span>
        </div>
        <ul className="flex flex-col divide-y divide-border">
          {rows.map((row) => (
            <li
              key={row.req}
              className="flex flex-wrap items-start gap-x-3 gap-y-1 py-3"
            >
              <Pill tone={row.tone}>{row.mark}</Pill>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-bold">{row.req}</span>
                <span className="block text-xs text-muted">{row.evidence}</span>
              </span>
            </li>
          ))}
        </ul>
      </PreviewCard>
    </FeatureSection>
  )
}

export function Prepare() {
  const claims = [
    { text: 'Led a team of four', tone: 'good', label: 'Verified' },
    { text: 'Offline-first sync', tone: 'info', label: 'Reworded' },
    { text: 'Regulated-industry controls', tone: 'warn', label: 'Confirm it' },
  ] as const
  return (
    <FeatureSection
      eyebrow="Prepare"
      title="Applications that stay true."
      body="Tailored CVs and cover letters are built only from facts you have confirmed. Anything new is flagged for you to approve."
      points={[
        'Separate profiles for each career track',
        'Fact check on every claim',
        'Export to PDF or DOCX',
      ]}
    >
      <PreviewCard
        title="Tailored CV · fact check"
        note="Anything not in your profile is flagged for you. Nothing is invented."
      >
        <ul className="flex flex-col divide-y divide-border">
          {claims.map((claim) => (
            <li
              key={claim.text}
              className="flex items-center justify-between gap-3 py-3"
            >
              <span className="text-sm font-bold">{claim.text}</span>
              <Pill tone={claim.tone}>{claim.label}</Pill>
            </li>
          ))}
        </ul>
      </PreviewCard>
    </FeatureSection>
  )
}

export function GetSeen() {
  const checks = [
    {
      mark: '✓ Pass',
      tone: 'good',
      title: 'Reads cleanly as plain text',
      note: 'No tables or columns to trip filters',
    },
    {
      mark: '✓ Pass',
      tone: 'good',
      title: 'Job title matches the posting',
      note: 'Senior Flutter Engineer',
    },
    {
      mark: '◐ Fix',
      tone: 'warn',
      title: 'Keywords: 9 of 11 present',
      note: 'Add Swift or HIPAA only if true',
    },
    {
      mark: '✓ Pass',
      tone: 'good',
      title: 'Hiring team contact found',
      note: 'Public team page',
    },
  ] as const
  return (
    <FeatureSection
      flip
      eyebrow="Get seen"
      title="Get past the filter and in front of a person."
      body="Many applications are rejected by software before a human reads them. Jobmigo will check how your CV reads to those systems, show what to fix, and help you reach the hiring team directly."
      points={[
        'Hiring-system readability check',
        'Keyword coverage, with truthful additions only',
        'Public hiring-team contacts and a drafted note',
      ]}
    >
      <PreviewCard
        title="Reachability check"
        note="A checklist, not a score. Every fix removes a reason to be filtered out."
      >
        <ul className="flex flex-col divide-y divide-border">
          {checks.map((check) => (
            <li
              key={check.title}
              className="flex flex-wrap items-start gap-x-3 gap-y-1 py-3"
            >
              <Pill tone={check.tone}>{check.mark}</Pill>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-bold">{check.title}</span>
                <span className="block text-xs text-muted">{check.note}</span>
              </span>
            </li>
          ))}
        </ul>
      </PreviewCard>
    </FeatureSection>
  )
}

export function StayInMotion() {
  const quests = [
    { text: 'Check your strong fits', xp: '+10 XP' },
    { text: 'Review a tailored CV', xp: '+20 XP' },
    { text: 'Send one follow-up', xp: '+15 XP' },
  ]
  return (
    <FeatureSection
      eyebrow="Stay in motion"
      title="Make progress feel like progress."
      body="Job searches are long and quiet. Migo will turn the small, useful steps into daily quests, streaks and badges, so you can see how far you have come."
      points={[
        'Rewards go to careful applications and follow-ups, never to volume.',
      ]}
    >
      <PreviewCard title="Today with Migo">
        <div className="flex flex-wrap gap-2">
          <Pill tone="warn">Day 6 streak</Pill>
          <Pill tone="info">Level 3 · Shortlister</Pill>
        </div>
        <ul className="flex flex-col divide-y divide-border">
          {quests.map((quest) => (
            <li
              key={quest.text}
              className="flex items-center justify-between gap-3 py-3"
            >
              <span className="text-sm font-bold">{quest.text}</span>
              <span className="text-sm font-extrabold text-accent-strong">
                {quest.xp}
              </span>
            </li>
          ))}
        </ul>
      </PreviewCard>
    </FeatureSection>
  )
}
