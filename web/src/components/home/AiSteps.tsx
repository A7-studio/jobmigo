const STEPS = [
  {
    title: 'Find live jobs',
    does: 'Reads postings and flags stale, reposted and ghost jobs before you waste time on them.',
    you: 'Which roles to chase.',
  },
  {
    title: 'Know your fit',
    does: 'Matches each requirement to evidence in your CV and names the gaps.',
    you: 'Whether it is worth applying.',
  },
  {
    title: 'Tailor your CV',
    does: 'Rewrites your CV for each role using only facts you have confirmed.',
    you: 'What goes in. Nothing is invented.',
  },
  {
    title: 'Pass the filters',
    does: "Checks your CV reads cleanly for hiring systems and covers the posting's keywords.",
    you: 'Which missing keywords are true for you.',
  },
  {
    title: 'Reach a person',
    does: 'Finds public hiring-team contacts and drafts a short, personal note.',
    you: 'Whether to send it, and when.',
  },
  {
    title: 'Follow up before you vanish',
    does: 'Spots applications that have gone quiet and drafts the nudge.',
    you: 'Who to chase.',
  },
]

export function AiSteps() {
  return (
    <section
      id="features"
      aria-labelledby="aih"
      className="flex flex-col gap-6 pb-20 md:pb-24"
    >
      <div className="flex max-w-3xl flex-col gap-3">
        <span className="text-sm font-bold text-accent-strong">
          AI-powered, human-approved
        </span>
        <h2 id="aih" className="text-3xl leading-tight font-bold md:text-4xl">
          AI that gets your application out of the pile.
        </h2>
        <p className="text-base leading-relaxed text-body md:text-lg">
          Most applications vanish into a ghost pipeline: filtered out by
          software, buried under hundreds of others, or sent to a job that was
          already closed. Jobmigo is being built to go after that problem, step
          by step. We aim to get you to the interview. Winning it is up to you.
        </p>
      </div>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {STEPS.map((step) => (
          <li
            key={step.title}
            className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5"
          >
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold">{step.title}</h3>
              <span className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-extrabold text-accent-soft-ink">
                AI
              </span>
            </div>
            <p className="text-sm leading-relaxed text-body">
              <strong className="text-ink">AI will:</strong> {step.does}
            </p>
            <p className="text-sm leading-relaxed text-body">
              <strong className="text-ink">You decide:</strong> {step.you}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}
