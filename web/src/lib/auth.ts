import { betterAuth } from 'better-auth'
import { jwt } from 'better-auth/plugins'
import { tanstackStartCookies } from 'better-auth/tanstack-start'
import { Pool } from 'pg'

function required(name: string): string {
  const value = process.env[name]
  if (!value) throw new Error(`Missing environment variable ${name}`)
  return value
}

const baseURL = required('BETTER_AUTH_URL')
const googleId = process.env.GOOGLE_CLIENT_ID
const googleSecret = process.env.GOOGLE_CLIENT_SECRET

export const googleEnabled = Boolean(googleId && googleSecret)

export const auth = betterAuth({
  baseURL,
  secret: required('BETTER_AUTH_SECRET'),
  database: new Pool({ connectionString: required('AUTH_DATABASE_URL') }),
  user: { modelName: 'auth_user' },
  session: { modelName: 'auth_session' },
  account: { modelName: 'auth_account' },
  verification: { modelName: 'auth_verification' },
  emailAndPassword: { enabled: true, minPasswordLength: 8 },
  socialProviders:
    googleId && googleSecret
      ? { google: { clientId: googleId, clientSecret: googleSecret } }
      : {},
  plugins: [
    jwt({
      schema: { jwks: { modelName: 'auth_jwks' } },
      jwks: { keyPairConfig: { alg: 'EdDSA', crv: 'Ed25519' } },
      jwt: {
        expirationTime: '15m',
        definePayload: ({ user }) => ({
          email: user.email,
          name: user.name,
          emailVerified: user.emailVerified,
        }),
      },
    }),
    tanstackStartCookies(),
  ],
})
