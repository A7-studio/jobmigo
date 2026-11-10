/** Pure rules for the Jobs screen: form checks, calm copy for every code, and small labels. */

export const LIMITS = {
  company: 120,
  title: 200,
  location: 120,
  url: 2000,
  textMin: 5,
  textMax: 100_000,
} as const

/** Whitespace collapses the way the engine does it, so lengths agree. */
export const tidy = (value: string) => value.replace(/\s+/g, ' ').trim()

export type AddForm = {
  company: string
  title: string
  location: string
  text: string
}

export type AddField = keyof AddForm | 'url'

export type AddResult =
  | {
      ok: true
      body: {
        company: string
        title: string
        text: string
        location?: string
        url?: string
      }
    }
  | { ok: false; errors: Partial<Record<AddField, string>> }

/** Check the add form and turn it into the request body the engine expects. */
export function checkAdd(form: AddForm, url: string | null): AddResult {
  const errors: Partial<Record<AddField, string>> = {}
  const company = tidy(form.company)
  const title = tidy(form.title)
  const location = tidy(form.location)
  if (company === '') errors.company = 'Add the company name.'
  else if (company.length > LIMITS.company) {
    errors.company = `Use ${LIMITS.company} characters or fewer (now ${company.length}).`
  }
  if (title === '') errors.title = 'Add the job title.'
  else if (title.length > LIMITS.title) {
    errors.title = `Use ${LIMITS.title} characters or fewer (now ${title.length}).`
  }
  if (location.length > LIMITS.location) {
    errors.location = `Use ${LIMITS.location} characters or fewer (now ${location.length}).`
  }
  const text = form.text.trim()
  if (text.length < LIMITS.textMin) {
    errors.text = 'Paste the posting text.'
  } else if (form.text.length > LIMITS.textMax) {
    errors.text = `That is too long. Keep it to ${LIMITS.textMax.toLocaleString('en-US')} characters.`
  }
  const link = url === null ? '' : url.trim()
  if (link !== '' && !readableLink(link)) {
    errors.url = 'Use a full web address that starts with http or https.'
  } else if (link.length > LIMITS.url) {
    errors.url = `Use ${LIMITS.url} characters or fewer.`
  }
  if (Object.keys(errors).length > 0) return { ok: false, errors }
  return {
    ok: true,
    body: {
      company,
      title,
      text: form.text,
      ...(location ? { location } : {}),
      ...(link ? { url: link } : {}),
    },
  }
}

/** True for an http or https address with a host and no embedded credentials. */
export function readableLink(value: string): boolean {
  try {
    const parsed = new URL(value)
    return (
      (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
      parsed.hostname !== '' &&
      parsed.username === '' &&
      parsed.password === ''
    )
  } catch {
    return false
  }
}

/** The host to show for a stored address, or null; only http and https addresses count. */
export function sourceHost(value: string | null): string | null {
  if (value === null || !readableLink(value)) return null
  return new URL(value).hostname.replace(/^www\./, '')
}

/** The address to link to, or null: never anything but http or https. */
export function safeHref(value: string | null): string | null {
  return value !== null && readableLink(value) ? new URL(value).href : null
}

/** The letter for the tile: the first letter or digit of the company, else a dot. */
export function initialOf(company: string): string {
  const match = /[\p{L}\p{N}]/u.exec(company)
  return match ? match[0].toUpperCase() : '·'
}

/** "Added today", "Added yesterday", "Added 3 days ago" or a date, from an ISO time. */
export function addedLabel(iso: string, now: Date = new Date()): string {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return ''
  const days = Math.floor(
    (startOfDay(now).getTime() - startOfDay(then).getTime()) / 86_400_000,
  )
  if (days <= 0) return 'Added today'
  if (days === 1) return 'Added yesterday'
  if (days < 14) return `Added ${days} days ago`
  return `Added ${then.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`
}

const startOfDay = (date: Date) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate())

type Copy = { title: string; body: string }

/** Calm wording for an error code; never shows a code or a raw server message. */
export function jobsCopy(code: string): Copy {
  switch (code) {
    case 'validation_failed':
      return {
        title: 'That was not accepted',
        body: 'Check the fields and the text, then try again. Nothing was saved.',
      }
    case 'already_exists':
      return {
        title: 'You already saved that job',
        body: 'A job with that link, or the same company and title, is already in your list.',
      }
    case 'limit_reached':
      return {
        title: 'Your list is full',
        body: 'You can keep up to five hundred jobs. Delete some you no longer need first.',
      }
    case 'fetch_blocked':
      return {
        title: 'We cannot read that link',
        body: 'It points somewhere we are not allowed to go. Paste the posting text instead.',
      }
    case 'robots_disallowed':
      return {
        title: 'That site asks not to be read',
        body: 'Its rules say automated visits are not welcome, so we left it alone. Paste the posting text instead.',
      }
    case 'robots_unreadable':
      return {
        title: 'We could not check that site’s rules',
        body: 'We only read pages when we are sure it is allowed. Paste the posting text instead.',
      }
    case 'not_a_page':
      return {
        title: 'That link is not a readable page',
        body: 'It may need you to sign in, may have moved, or may be a file. Paste the posting text instead.',
      }
    case 'too_large':
      return {
        title: 'That page is too large',
        body: 'Paste just the posting text instead.',
      }
    case 'fetch_failed':
      return {
        title: 'We could not reach that page',
        body: 'The site did not answer in time. Try again, or paste the posting text instead.',
      }
    case 'rate_limited':
      return {
        title: 'Too many links at once',
        body: 'Wait a minute and try again, or paste the posting text now.',
      }
    case 'not_found':
      return {
        title: 'That job is no longer there',
        body: 'It may have been removed in another tab. We refreshed the list.',
      }
    case 'network':
      return {
        title: 'We could not reach Jobmigo',
        body: 'Check your connection and try again. Nothing changed.',
      }
    default:
      return {
        title: 'Something went wrong',
        body: 'Try again in a moment. Your jobs are unchanged.',
      }
  }
}

/** Codes after which the best next step is to paste the text instead of the link. */
export const PASTE_INSTEAD = new Set([
  'fetch_blocked',
  'robots_disallowed',
  'robots_unreadable',
  'not_a_page',
  'too_large',
  'fetch_failed',
  'rate_limited',
])

/** A page title as a starting point for the job title: trimmed to the limit. */
export function titleHint(pageTitle: string | null): string {
  return pageTitle === null ? '' : tidy(pageTitle).slice(0, LIMITS.title)
}
