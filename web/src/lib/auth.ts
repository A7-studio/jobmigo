import { betterAuth } from 'better-auth'
import { drizzleAdapter } from 'better-auth/adapters/drizzle'
import { tanstackStartCookies } from 'better-auth/tanstack-start'
import { getDb } from '#/server/db/client'
import {
  authAccount,
  authSession,
  authUser,
  authVerification,
} from '#/server/db/schema'

function required(name: string): string {
  const value = process.env[name]
  if (!value) throw new Error(`Missing environment variable ${name}`)
  return value
}

const googleId = process.env.GOOGLE_CLIENT_ID
const googleSecret = process.env.GOOGLE_CLIENT_SECRET

export const googleEnabled = Boolean(googleId && googleSecret)

export const auth = betterAuth({
  baseURL: required('BETTER_AUTH_URL'),
  secret: required('BETTER_AUTH_SECRET'),
  database: drizzleAdapter(getDb(), {
    provider: 'pg',
    schema: { authUser, authSession, authAccount, authVerification },
  }),
  user: { modelName: 'authUser' },
  session: { modelName: 'authSession' },
  account: { modelName: 'authAccount', accountLinking: { enabled: false } },
  verification: { modelName: 'authVerification' },
  emailAndPassword: { enabled: true, minPasswordLength: 8 },
  socialProviders:
    googleId && googleSecret
      ? { google: { clientId: googleId, clientSecret: googleSecret } }
      : {},
  plugins: [tanstackStartCookies()],
})
