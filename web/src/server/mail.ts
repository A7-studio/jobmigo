import { logger } from './logger'

export type EmailMessage = {
  to: string
  subject: string
  html: string
  text: string
  headers?: Record<string, string>
}

export interface EmailProvider {
  send: (message: EmailMessage) => Promise<void>
}

type FetchLike = (input: string, init: RequestInit) => Promise<Response>

/** Sends through the Resend HTTP API. No SDK: one POST. */
export class ResendProvider implements EmailProvider {
  private readonly apiKey: string
  private readonly from: string
  private readonly fetchFn: FetchLike

  constructor(apiKey: string, from: string, fetchFn: FetchLike = fetch) {
    this.apiKey = apiKey
    this.from = from
    this.fetchFn = fetchFn
  }

  async send(message: EmailMessage): Promise<void> {
    const response = await this.fetchFn('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        authorization: `Bearer ${this.apiKey}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        from: this.from,
        to: [message.to],
        subject: message.subject,
        html: message.html,
        text: message.text,
        headers: message.headers,
      }),
    })
    if (!response.ok) {
      throw new Error(`Resend responded with status ${response.status}`)
    }
  }
}

/** Local development only: prints the message (no recipient) so links can be followed. */
export class ConsoleProvider implements EmailProvider {
  send(message: EmailMessage): Promise<void> {
    logger.info('email (console provider)', {
      subject: message.subject,
      text: message.text,
    })
    return Promise.resolve()
  }
}

class UnconfiguredProvider implements EmailProvider {
  send(): Promise<void> {
    return Promise.reject(
      new Error('Email is not configured: set RESEND_API_KEY and MAIL_FROM.'),
    )
  }
}

let provider: EmailProvider | undefined

export function getEmailProvider(): EmailProvider {
  if (provider) return provider
  const apiKey = process.env.RESEND_API_KEY
  const from = process.env.MAIL_FROM
  if (apiKey) {
    if (!from) throw new Error('Missing environment variable MAIL_FROM')
    provider = new ResendProvider(apiKey, from)
  } else if (process.env.ENVIRONMENT === 'local') {
    provider = new ConsoleProvider()
  } else {
    provider = new UnconfiguredProvider()
  }
  return provider
}
