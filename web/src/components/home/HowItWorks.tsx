import { Reveal } from './Reveal'

const STEPS = [
  {
    title: 'Upload your CV',
    body: 'PDF or DOCX. Migo will read it in about a minute.',
  },
  {
    title: 'Review your profile',
    body: 'Confirm each fact. Make a profile for every track you want.',
  },
  {
    title: 'Set what matters',
    body: 'Salary floor, location, dealbreakers and must-haves.',
  },
  {
    title: 'See your fit',
    body: 'Paste a job link and get an honest, evidence-based evaluation. Automatic daily shortlists come later.',
  },
]

export function HowItWorks() {
  return (
    <Reveal>
      <section
        id="how"
        aria-labelledby="how-h"
        className="flex flex-col gap-6 pb-20 md:pb-24"
      >
        <h2 id="how-h" className="text-3xl leading-tight font-bold md:text-4xl">
          How it will work: four steps to your first honest evaluation.
        </h2>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <li
              key={step.title}
              className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5"
            >
              <span className="grid size-9 place-items-center rounded-full bg-accent-soft font-display text-lg font-bold text-accent-soft-ink">
                {index + 1}
              </span>
              <h3 className="text-lg font-semibold">{step.title}</h3>
              <p className="text-sm leading-relaxed text-body">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>
    </Reveal>
  )
}
