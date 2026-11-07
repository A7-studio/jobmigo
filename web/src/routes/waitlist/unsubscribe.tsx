import { useState } from 'react'
import { Link, createFileRoute } from '@tanstack/react-router'
import { LINK_BUTTON, MessagePage } from '#/components/MessagePage'
import { unsubscribeWaitlistFn } from '#/lib/waitlist.functions'

export const Route = createFileRoute('/waitlist/unsubscribe')({
  validateSearch: (search: Record<string, unknown>) => ({
    token: typeof search.token === 'string' ? search.token : '',
  }),
  head: () => ({ meta: [{ title: 'Unsubscribe | Jobmigo' }] }),
  component: Unsubscribe,
})

type State = 'idle' | 'working' | 'done' | 'invalid' | 'failed'

function Unsubscribe() {
  const { token } = Route.useSearch()
  const [state, setState] = useState<State>(token ? 'idle' : 'invalid')

  async function onClick() {
    setState('working')
    try {
      const result = await unsubscribeWaitlistFn({ data: { token } })
      setState(result === 'unsubscribed' ? 'done' : 'invalid')
    } catch {
      setState('failed')
    }
  }

  if (state === 'done') {
    return (
      <MessagePage title="You are unsubscribed">
        <p>We will not email you about Jobmigo again.</p>
        <Link to="/" className={LINK_BUTTON}>
          Back to Jobmigo
        </Link>
      </MessagePage>
    )
  }
  if (state === 'invalid') {
    return (
      <MessagePage title="This link does not work">
        <p>
          It may be incomplete or already replaced. If you still get our email,
          reply to it and we will remove you by hand.
        </p>
        <Link to="/" className={LINK_BUTTON}>
          Back to Jobmigo
        </Link>
      </MessagePage>
    )
  }
  return (
    <MessagePage title="Unsubscribe from Jobmigo emails?">
      <p>You will stop receiving waitlist and launch emails.</p>
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
        {state === 'working' ? 'Unsubscribing…' : 'Unsubscribe'}
      </button>
    </MessagePage>
  )
}
