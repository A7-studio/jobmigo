import { Link, createFileRoute } from '@tanstack/react-router'
import { getSiteConfig } from '#/lib/site.functions'

export const Route = createFileRoute('/privacy')({
  loader: () => getSiteConfig(),
  head: () => ({ meta: [{ title: 'Privacy notice | Jobmigo' }] }),
  component: Privacy,
})

function Privacy() {
  const { contactEmail } = Route.useLoaderData()
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-4 py-10">
      <Link to="/" className="font-display text-2xl font-semibold text-ink">
        job<span className="text-accent-strong">migo</span>
      </Link>
      <h1 className="text-3xl font-bold">Privacy notice</h1>
      <p className="text-body">
        This notice covers the Jobmigo waitlist and what happens to a CV if you
        upload one. Jobmigo is a product of A7Studio.
      </p>

      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">What we collect</h2>
        <ul className="list-disc pl-6 text-body">
          <li>Your email address.</li>
          <li>
            When you agreed to hear from us and which version of the wording you
            saw.
          </li>
          <li>
            Where you came from, if the link you used carried a source tag (for
            example a campaign name). We do not store your IP address ourselves.
          </li>
        </ul>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Why</h2>
        <p className="text-body">
          To send you a confirmation email, tell you when early access opens,
          and share launch updates. We do not sell or share your email for
          advertising.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Who handles it</h2>
        <p className="text-body">
          Our email provider, Resend, sends our emails for us. They process your
          address only to deliver them. The pages load fonts from Google Fonts,
          so your browser contacts Google when you visit, and Google can see
          your IP address.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Your CV</h2>
        <p className="text-body">
          If you upload a CV (PDF or DOCX), we keep the file in private storage
          and keep the text we read from it, both tied to your account. Only you
          can open or delete them. Deleting a CV also deletes any profile draft
          made from it.
        </p>
        <p className="text-body">
          Only when you ask us to read your CV into a profile draft, we send the
          CV text (not the file) to our AI provider, DeepSeek, which returns the
          draft. We do not send it for any other reason. Our usage records keep
          counts and costs only, never the text. How DeepSeek handles what it
          receives is covered by its own privacy policy.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">How long we keep it</h2>
        <p className="text-body">
          Until you unsubscribe. After that we keep a small record (your email
          address, the dates you agreed and unsubscribed, and any source tag) so
          we can make sure we never email you again. Every email has an
          unsubscribe link.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Your choices</h2>
        <p className="text-body">
          You can unsubscribe at any time from the link in any email.{' '}
          {contactEmail ? (
            <>
              To ask for your data to be deleted completely, write to{' '}
              <a
                href={`mailto:${contactEmail}`}
                className="font-bold text-accent-strong underline"
              >
                {contactEmail}
              </a>
              .
            </>
          ) : (
            'To ask for your data to be deleted completely, reply to any of our emails.'
          )}
        </p>
      </section>

      <Link
        to="/"
        className="inline-flex min-h-11 items-center self-start font-bold text-accent-strong underline"
      >
        Back to Jobmigo
      </Link>
    </main>
  )
}
