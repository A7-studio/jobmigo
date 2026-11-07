const STEPS = [
  'Discover',
  'Verify',
  'Evaluate',
  'Tailor',
  'Check',
  'Reach out',
  'Apply',
  'Follow up',
]

export function Journey() {
  return (
    <section
      aria-labelledby="journey"
      className="flex flex-col items-center gap-5 pb-16 text-center md:pb-20"
    >
      <h2 id="journey" className="text-xl font-bold md:text-2xl">
        From job post to interview invite
      </h2>
      <ol className="flex flex-wrap justify-center gap-2.5">
        {STEPS.map((step, index) => (
          <li
            key={step}
            className="flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2.5 text-sm font-bold"
          >
            <span className="grid size-6 place-items-center rounded-full bg-accent-soft text-xs font-extrabold text-accent-soft-ink">
              {index + 1}
            </span>
            {step}
          </li>
        ))}
      </ol>
    </section>
  )
}
