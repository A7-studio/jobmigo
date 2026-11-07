import { useState } from 'react'
import { Link, createFileRoute } from '@tanstack/react-router'
import { LINK_BUTTON, MessagePage } from '#/components/MessagePage'
import { confirmWaitlistFn } from '#/lib/waitlist.functions'

// Loading this page confirms nothing: mail scanners and link previews fetch emailed
// links. Only pressing the button calls the server function.
export const Route = createFileRoute('/waitlist/confirm')({
  validateSearch: (search: Record<string, unknown>) => ({
    token: typeof search.token === 'string' ? search.token : '',
  }),
  head: () => ({ meta: [{ title: 'Confirm your email | Jobmigo' }] }),
  component: Confirm,
})

type State =
  | 'idle'
  | 'working'
  | 'failed'
  | 'confirmed'
  | 'already_confirmed'
  | 'expired'
  | 'invalid'

const RESULTS = {
  confirmed: {
    title: "You're on the list",
    body: 'Thanks for confirming. We will email you when early access opens.',
  },
  already_confirmed: {
    title: "You're already confirmed",
    body: 'Nothing more to do. We will email you when early access opens.',
  },
  expired: {
    title: 'This link has expired',
    body: 'Join the waitlist again from the homepage and we will send a fresh link.',
  },
  invalid: {
    title: 'This link does not work',
    body: 'It may have been replaced by a newer email, or you may have unsubscribed. Join again from the homepage if you like.',
  },
} as const

function Confirm() {
  const { token } = Route.useSearch()
  const [state, setState] = useState<State>(token ? 'idle' : 'invalid')

  async function onClick() {
    setState('working')
    try {
      setState(await confirmWaitlistFn({ data: { token } }))
    } catch {
      setState('failed')
    }
  }

  if (state !== 'idle' && state !== 'working' && state !== 'failed') {
    const copy = RESULTS[state]
    return (
      <MessagePage title={copy.title}>
        <p>{copy.body}</p>
        <Link to="/" className={LINK_BUTTON}>
          Back to Jobmigo
        </Link>
      </MessagePage>
    )
  }
  return (
    <MessagePage title="Confirm your email">
      <p>One last step: press the button to join the Jobmigo waitlist.</p>
      {state === 'failed' && (
        <p className="font-semibold text-alert">
          Something went wrong. Please try again.
        </p>
      )}
      <button
        type="button"
        onClick={onClick}
        disabled={state === 'working'}
        className="min-h-11 rounded-full bg-accent-strong px-5 font-bold text-white hover:bg-accent-strong-hover disabled:opacity-70"
      >
        {state === 'working' ? 'Confirming…' : 'Confirm my email'}
      </button>
    </MessagePage>
  )
}
