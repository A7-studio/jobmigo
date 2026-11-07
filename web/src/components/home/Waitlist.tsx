import { Migo } from '#/components/Migo'
import { WaitlistForm } from '#/components/WaitlistForm'

export function Waitlist() {
  return (
    <section
      id="waitlist"
      aria-labelledby="waitlist-h"
      className="mb-16 flex flex-wrap items-center gap-8 rounded-2xl bg-accent-wash p-6 sm:p-10"
    >
      <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-3">
        <Migo size={72} />
        <h2
          id="waitlist-h"
          className="text-3xl leading-tight font-bold md:text-4xl"
        >
          Ready to meet your migo?
        </h2>
        <p className="text-base leading-relaxed text-body">
          Join the waitlist for early access. Early members get founding-member
          pricing. We will only email you about Jobmigo, and you can unsubscribe
          any time.
        </p>
      </div>
      <div className="min-w-0 flex-[1_1_340px]">
        <WaitlistForm />
      </div>
    </section>
  )
}
