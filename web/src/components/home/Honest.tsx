const PRINCIPLES = [
  {
    title: 'We never invent experience',
    body: 'Every sentence in a CV or letter comes from facts you confirmed. New claims wait for your yes.',
  },
  {
    title: 'We never auto-apply',
    body: 'You review and send everything yourself. No spam to employers, no surprises.',
  },
  {
    title: 'Your data is yours',
    body: 'Your CV is private. Export it or delete it whenever you like.',
  },
  {
    title: 'AI proposes, you decide',
    body: 'AI output is always labelled and shows its evidence. You approve before anything leaves Jobmigo.',
  },
]

export function Honest() {
  return (
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
  )
}
