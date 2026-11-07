import { Reveal } from './Reveal'

const PRINCIPLES = [
  {
    title: 'We will never invent experience',
    body: 'Every sentence in a CV or letter will come from facts you confirmed. New claims will wait for your yes.',
  },
  {
    title: 'We will never auto-apply',
    body: 'You will review and send everything yourself. No spam to employers, no surprises.',
  },
  {
    title: 'Your data is yours',
    body: 'Your CV will be private, and you will be able to export or delete it whenever you like.',
  },
  {
    title: 'AI proposes, you decide',
    body: 'AI output will be labelled and show its evidence. You approve before anything leaves Jobmigo.',
  },
]

export function Honest() {
  return (
    <Reveal>
      <section
        id="honest"
        aria-labelledby="honest-h"
        className="flex flex-col gap-6 pb-20 md:pb-24"
      >
        <h2
          id="honest-h"
          className="text-3xl leading-tight font-bold md:text-4xl"
        >
          Honest by design.
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2">
          {PRINCIPLES.map((item) => (
            <li
              key={item.title}
              className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-5"
            >
              <h3 className="text-lg font-semibold">{item.title}</h3>
              <p className="text-sm leading-relaxed text-body">{item.body}</p>
            </li>
          ))}
        </ul>
      </section>
    </Reveal>
  )
}
