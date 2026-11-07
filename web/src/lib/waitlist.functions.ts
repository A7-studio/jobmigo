import { createServerFn } from '@tanstack/react-start'
import { getRequestHeaders } from '@tanstack/react-start/server'
import { z } from 'zod'

export const joinWaitlistFn = createServerFn({ method: 'POST' })
  .validator(async (input: unknown) => {
    const { joinInputSchema } = await import('#/server/waitlist-api')
    return joinInputSchema.parse(input)
  })
  .handler(async ({ data }) => {
    const { handleJoin } = await import('#/server/waitlist-api')
    return handleJoin(data, getRequestHeaders())
  })

const tokenSchema = z.object({ token: z.string().max(200) })

export const confirmWaitlistFn = createServerFn({ method: 'POST' })
  .validator((input: unknown) => tokenSchema.parse(input))
  .handler(async ({ data }) => {
    const { confirmWaitlist } = await import('#/server/waitlist')
    return confirmWaitlist(data.token)
  })

export const unsubscribeWaitlistFn = createServerFn({ method: 'POST' })
  .validator((input: unknown) => tokenSchema.parse(input))
  .handler(async ({ data }) => {
    const { unsubscribeWaitlist } = await import('#/server/waitlist')
    return unsubscribeWaitlist(data.token)
  })
