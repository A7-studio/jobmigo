import { sql } from 'drizzle-orm'
import {
  boolean,
  check,
  index,
  integer,
  jsonb,
  numeric,
  pgTable,
  primaryKey,
  text,
  timestamp,
  uuid,
} from 'drizzle-orm/pg-core'

const createdAt = () =>
  timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
const updatedAt = () =>
  timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()

// App tables ------------------------------------------------------------

export const user = pgTable(
  'user',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    authSubject: text('auth_subject').notNull().unique(),
    email: text('email').notNull().unique(),
    displayName: text('display_name'),
    locale: text('locale').notNull().default('en'),
    timezone: text('timezone').notNull().default('Africa/Nairobi'),
    status: text('status').notNull().default('active'),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => [
    check(
      'ck_user_status',
      sql`${t.status} in ('active', 'suspended', 'deleted')`,
    ),
  ],
)

export const role = pgTable('role', {
  id: uuid('id').primaryKey().defaultRandom(),
  name: text('name').notNull().unique(),
})

export const rolePermission = pgTable(
  'role_permission',
  {
    roleId: uuid('role_id')
      .notNull()
      .references(() => role.id, { onDelete: 'cascade' }),
    permission: text('permission').notNull(),
  },
  (t) => [primaryKey({ columns: [t.roleId, t.permission] })],
)

export const staffMember = pgTable('staff_member', {
  userId: uuid('user_id')
    .primaryKey()
    .references(() => user.id, { onDelete: 'cascade' }),
  roleId: uuid('role_id')
    .notNull()
    .references(() => role.id),
  mfaEnforced: boolean('mfa_enforced').notNull().default(true),
  createdAt: createdAt(),
})

export const auditLog = pgTable(
  'audit_log',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    staffId: uuid('staff_id')
      .notNull()
      .references(() => staffMember.userId),
    action: text('action').notNull(),
    targetType: text('target_type').notNull(),
    targetId: uuid('target_id'),
    before: jsonb('before'),
    after: jsonb('after'),
    reason: text('reason').notNull(),
    ip: text('ip'),
    at: timestamp('at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [
    check('ck_audit_log_reason_not_empty', sql`length(trim(${t.reason})) > 0`),
  ],
)

// Better Auth tables (names mapped in src/lib/auth.ts) -------------------

export const authUser = pgTable('auth_user', {
  id: text('id').primaryKey(),
  name: text('name').notNull(),
  email: text('email').notNull().unique(),
  emailVerified: boolean('email_verified').notNull().default(false),
  image: text('image'),
  createdAt: createdAt(),
  updatedAt: updatedAt(),
})

export const authSession = pgTable(
  'auth_session',
  {
    id: text('id').primaryKey(),
    expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
    token: text('token').notNull().unique(),
    createdAt: createdAt(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull(),
    ipAddress: text('ip_address'),
    userAgent: text('user_agent'),
    userId: text('user_id')
      .notNull()
      .references(() => authUser.id, { onDelete: 'cascade' }),
  },
  (t) => [index('auth_session_user_id_idx').on(t.userId)],
)

export const authAccount = pgTable(
  'auth_account',
  {
    id: text('id').primaryKey(),
    accountId: text('account_id').notNull(),
    providerId: text('provider_id').notNull(),
    userId: text('user_id')
      .notNull()
      .references(() => authUser.id, { onDelete: 'cascade' }),
    accessToken: text('access_token'),
    refreshToken: text('refresh_token'),
    idToken: text('id_token'),
    accessTokenExpiresAt: timestamp('access_token_expires_at', {
      withTimezone: true,
    }),
    refreshTokenExpiresAt: timestamp('refresh_token_expires_at', {
      withTimezone: true,
    }),
    scope: text('scope'),
    password: text('password'),
    createdAt: createdAt(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull(),
  },
  (t) => [index('auth_account_user_id_idx').on(t.userId)],
)

export const authVerification = pgTable(
  'auth_verification',
  {
    id: text('id').primaryKey(),
    identifier: text('identifier').notNull(),
    value: text('value').notNull(),
    expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => [index('auth_verification_identifier_idx').on(t.identifier)],
)

// Waitlist (feature 28a) ---------------------------------------------------

export const waitlistSignup = pgTable(
  'waitlist_signup',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    email: text('email').notNull().unique(),
    status: text('status').notNull().default('pending'),
    consentTextVersion: text('consent_text_version').notNull(),
    consentedAt: timestamp('consented_at', { withTimezone: true }).notNull(),
    source: text('source'),
    tokenHash: text('token_hash').notNull(),
    tokenSentAt: timestamp('token_sent_at', { withTimezone: true }).notNull(),
    emailsSent: integer('emails_sent').notNull().default(1),
    confirmedAt: timestamp('confirmed_at', { withTimezone: true }),
    unsubscribedAt: timestamp('unsubscribed_at', { withTimezone: true }),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => [
    check(
      'ck_waitlist_signup_status',
      sql`${t.status} in ('pending', 'confirmed', 'unsubscribed')`,
    ),
    index('waitlist_signup_token_hash_idx').on(t.tokenHash),
  ],
)

// AI gateway ------------------------------------------------------------

export const AI_WORKFLOWS = [
  'parse',
  'screen',
  'evaluate',
  'tailor',
  'reach_check',
  'outreach',
] as const

/** One row per model response received, plus one per cache hit. Holds no text. */
export const usageEvent = pgTable(
  'usage_event',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    userId: uuid('user_id')
      .notNull()
      .references(() => user.id, { onDelete: 'cascade' }),
    workflow: text('workflow').notNull(),
    provider: text('provider').notNull(),
    model: text('model').notNull(),
    promptVersion: text('prompt_version').notNull(),
    tokensIn: integer('tokens_in').notNull(),
    tokensOut: integer('tokens_out').notNull(),
    costUsd: numeric('cost_usd', { precision: 12, scale: 6 }),
    cacheHit: boolean('cache_hit').notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    check(
      'ck_usage_event_workflow',
      sql`${t.workflow} in ('parse', 'screen', 'evaluate', 'tailor', 'reach_check', 'outreach')`,
    ),
    check(
      'ck_usage_event_tokens',
      sql`${t.tokensIn} >= 0 and ${t.tokensOut} >= 0`,
    ),
    index('usage_event_user_created_idx').on(t.userId, t.createdAt),
  ],
)

/** Validated model output, keyed per user so results are never shared. */
export const aiCache = pgTable(
  'ai_cache',
  {
    userId: uuid('user_id')
      .notNull()
      .references(() => user.id, { onDelete: 'cascade' }),
    cacheKey: text('cache_key').notNull(),
    task: text('task').notNull(),
    promptVersion: text('prompt_version').notNull(),
    output: jsonb('output').notNull(),
    createdAt: createdAt(),
  },
  (t) => [primaryKey({ columns: [t.userId, t.cacheKey] })],
)
