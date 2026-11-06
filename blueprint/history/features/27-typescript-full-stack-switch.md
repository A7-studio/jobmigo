# Feature: TypeScript full-stack switch

**From build-plan:** feature 27
**Build attempt:** 1
**Branch:** feature/typescript-full-stack-switch
**Status:** verified

## Goal

Jobmigo runs as one TypeScript app. The TanStack Start server (in `web/`) does
what the FastAPI service did: Better Auth sessions identify the user, a
server-side `requireUser` maps a session to an app `user` row, per-user data
scoping, staff permissions and the append-only audit log are enforced in server
code, and the database is owned by Drizzle migrations. `api/` is deleted. Every
behaviour feature 1 delivered still works, with no JWT, JWKS or OpenAPI hop.

## In scope

- **Database layer:** `drizzle-orm` + `drizzle-kit` on the existing `pg` driver,
  one schema file, one baseline migration. Tables: `user`, `role`,
  `role_permission`, `staff_member`, `audit_log`, and the Better Auth tables
  (`auth_user`, `auth_session`, `auth_account`, `auth_verification`). The
  `auth_jwks` table is dropped. DB columns are snake_case, TypeScript fields
  camelCase. The baseline migration also seeds the four roles with the frozen
  permission matrix and installs the `audit_log` immutability trigger.
- **Better Auth** moves to the Drizzle adapter on the same schema. The JWT plugin
  is removed. `account.accountLinking` is disabled (review finding F-04).
- **Server foundations** in `web/src/server/`: stable error type, JSON logger
  with request IDs, `requireUser`, `requirePermission`, owner-scoping helpers,
  `recordAudit`, `GET /healthz`, `GET /readyz`, and a `getMe` server function.
- **Web client** drops the API client and generated types; `useMe` calls
  `getMe`. The sign-in and sign-up forms clear the query cache after success
  (review finding F-01).
- **Removal of FastAPI:** `api/`, its Docker service, Python entries in
  `.gitignore`, `.env.example` and `AGENTS.md`, and the docs that describe it.
- **Vitest** with a real Postgres test database.

## Out of scope

- The background worker and pg-boss (arrives with the first feature that queues
  work), Zod and request validation schemas (feature 28 adds them with the first
  public form), email, the waitlist, deployment, two-factor for staff, email
  verification, Google sign-in testing, any admin UI.
- Migrating existing dev data. There is none worth keeping: the dev database is
  reset and the baseline migration is applied to an empty one.
- Republishing the Technical Design artifact (the markdown docs are updated here;
  the artifact is a separate follow-up).

## Build loop

`workflow.stepReview` is `feature`: build all steps in order, run the narrow
check for each, run the full gate once at the end, then present one review
packet. `workflow.checkpointCommits` is disabled; `/complete` makes the commit.

## Build steps

- [x] **1. Dependencies, database client, schema and baseline migration.**
  Add `drizzle-orm`, `drizzle-kit` (dev) and `vitest` (dev). Add
  `web/drizzle.config.ts` reading `DATABASE_URL`, `web/src/server/db/client.ts`
  (one `pg` Pool, created lazily, exported `db`), `web/src/server/db/schema.ts`
  (all tables below) and generate the baseline migration with `drizzle-kit`, then
  append hand-written SQL to it for the role and permission seed and the
  `audit_log_immutable()` trigger. Add scripts `db:generate`, `db:migrate`,
  `test`, `typecheck` (`tsc --noEmit`). Make `.env` values reach scripts and the
  dev server (Node `--env-file-if-exists=../.env`, not a new dependency). Add
  Vitest global setup that creates `jobmigo_test` if missing and applies the
  migrations; refuse to run unless the database name ends in `_test` (review
  finding F-02).
  *Done when:* on an empty dev database `npm run db:migrate` succeeds; `npm test`
  has passing schema tests for every table's columns, the seeded roles and
  permission matrix, user defaults, the `status` check, the unique constraints,
  the audit reason check, and the immutability trigger (an UPDATE or DELETE on
  `audit_log` raises); `npm run build` and `npm run lint` pass.

- [x] **2. Better Auth on the Drizzle adapter, health routes.**
  In `src/lib/auth.ts` replace the `pg` Pool with `drizzleAdapter(db, { provider:
  'pg', schema })`, remove the `jwt` plugin and its `modelName` mappings, keep
  `emailAndPassword` (min 8), Google only when both variables are set, and
  `tanstackStartCookies()` last; set `account.accountLinking.enabled` to false.
  Use `@better-auth/cli generate` once in a scratch run to confirm the schema
  matches what Better Auth requires. Move the shared database variable to
  `DATABASE_URL` and drop `AUTH_DATABASE_URL`. Add `src/routes/healthz.ts`
  (`{ status: "ok" }`) and `src/routes/readyz.ts` (runs `select 1`; 503 with the
  stable error shape when the database is unreachable).
  *Done when:* `npm run build`, `npm run lint` and `npm test` pass; with the
  database and dev server running, sign-up and sign-in through `/api/auth/*`
  succeed, a wrong password is rejected, `/api/auth/token` and `/api/auth/jwks`
  no longer exist, `/healthz` returns ok and `/readyz` returns ok (live check run
  during implementation, no external accounts).

- [x] **3. Errors, logging, `requireUser` and `getMe`.**
  `src/server/errors.ts`: `DomainError` (`status`, `code`, `message`) with
  `NotFoundError`, `PermissionDeniedError`, `UnauthorizedError`, `ConflictError`,
  and a `toResult` helper that maps any thrown value to `{ code, message }`
  (unexpected errors become `internal_error` with a generic message and are
  logged, never leaked). `src/server/logger.ts`: one JSON line per event (level,
  time, message, request id) with no personal data, and a request ID taken from
  `X-Request-Id` or generated, returned on the response (check the installed
  TanStack Start version for global request middleware; if absent, wrap handlers
  in one helper). `src/server/identity.ts`: `requireUser(headers)` reads the Better
  Auth session (injectable for tests), creates the `user` row on first request
  with `insert ... on conflict (auth_subject) do nothing` and re-selects (lowercase
  email, `display_name` from the session name, defaults `en`, `Africa/Nairobi`,
  `active`), throws `UnauthorizedError` with no session, `PermissionDeniedError`
  when `status` is not `active`, and `ConflictError` when the email already belongs
  to another `auth_subject`. `getMe` is a server function returning `{ ok: true,
  me }` or `{ ok: false, code, message }` where `me` has `id`, `email`,
  `displayName`, `locale`, `timezone` and `staff` (`{ role, permissions }` or
  `null`). `auth_subject` is never returned.
  *Done when:* Vitest tests cover first-request creation, concurrent first
  requests creating one row, no session (unauthorized), suspended and deleted users
  (forbidden), the email conflict, `getMe` shape with and without a staff row, the
  unexpected-error mapping, and that logs contain no email or token; `npm run
  build`, `npm run lint` and `npm test` pass.

- [x] **4. Owner scoping, staff permissions and audit recorder.**
  `src/server/ownership.ts`: `ownedBy(table, userId)` returns the `user_id`
  condition, and `findOwned`, `listOwned`, `updateOwned`, `deleteOwned` helpers
  that always include it and return `null` or `false` for another user's row.
  `src/server/permissions.ts`: the permission constants and `ROLE_PERMISSIONS`
  matrix (identical to the frozen seed). `requirePermission(headers, permission)`
  builds on `requireUser` and loads the staff row and role; non-staff, a role
  without the permission and a suspended user all raise `PermissionDeniedError`.
  `src/server/audit.ts`: `recordAudit(tx, staff, input)` appends a row inside the
  caller's transaction and rejects an empty or whitespace reason with a
  `DomainError` (`reason_required`) before touching the database.
  *Done when:* tests show another user's row cannot be read, updated or deleted
  through the helpers (using a test-only table created in the test setup);
  non-staff, wrong role and suspended staff are refused while the right role
  passes; the matrix constant equals the seeded `role_permission` rows; the audit
  recorder rejects a blank reason and writes a row otherwise; `npm run build`,
  `npm run lint` and `npm test` pass.

- [x] **5. Web client switch.**
  Delete `src/lib/api.ts`, `src/lib/api-types.ts`, the `api:types` script, the
  `openapi-typescript` dependency, the `.npmrc` `legacy-peer-deps` line (if no
  other package needs it) and `VITE_API_URL`. `useMe` calls `getMe` through
  TanStack Query. The dashboard treats `code: "unauthorized"` as a redirect to
  `/sign-in` and any other failure as the existing error card with Retry.
  `AuthForm` clears the query cache (and any cached `me`) after a successful
  sign-in or sign-up before navigating. Sign out still clears the cache. The
  `_app` layout and `/` redirect keep using `getSession`.
  *Done when:* `npm run build`, `npm run lint`, `npm run typecheck` and `npm test`
  pass; in a browser against the running app: invalid email, short password,
  duplicate email and wrong password each show the right message; a valid sign-up
  and a sign-in land on `/dashboard` showing the user's name; signing in as a
  second user in the same tab shows that user, not the first; a signed-out visit
  to `/dashboard` lands on `/sign-in`; with `getMe` failing the error card and Retry
  recover; sign out returns to `/sign-in`; the layout has no horizontal scroll at
  390px.

- [x] **6. Remove FastAPI, update compose, env and docs.**
  Delete `api/` entirely. `docker-compose.yml` keeps `db` and `web` (web gets
  `DATABASE_URL`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, optional `GOOGLE_*`;
  no `api` service, no port 8001). Update `.env.example` (`DATABASE_URL`,
  `TEST_DATABASE_URL`, `BETTER_AUTH_*`, optional `GOOGLE_*`; drop the JWKS,
  issuer, `WEB_ORIGIN`, `VITE_API_URL` and Python-only entries), `.gitignore`
  (remove Python entries), `AGENTS.md` Commands (real commands: dev, build, lint,
  typecheck, `npm test`, `db:generate`, `db:migrate`, database reset
  `docker compose down -v` then `docker compose up -d db`, and a declared
  `Verify` command `npm run lint && npm run typecheck && npm run build && npm
  test` run in `web/`), `docs/technical-design.md` and `docs/database-design.md`
  (single TypeScript server, Drizzle, no JWT or JWKS, snake_case columns,
  dropped `auth_jwks`).
  *Done when:* a fresh clone can follow `AGENTS.md` and `.env.example` to start
  the database, migrate it, run the dev server and sign up; `docker compose
  config` is valid; no file outside `blueprint/history/` mentions FastAPI,
  Alembic, SQLAlchemy, `uv`, JWKS or port 8001; the `Verify` command passes.

## Files / areas

- `web/src/server/` (new): `db/client.ts`, `db/schema.ts`, `errors.ts`,
  `logger.ts`, `identity.ts`, `ownership.ts`, `permissions.ts`, `audit.ts`.
- `web/drizzle/` (new): generated baseline migration plus the appended seed and
  trigger SQL; `web/drizzle.config.ts`.
- `web/vitest.config.ts` and `web/tests/` (new): global setup and tests.
- `web/src/lib/auth.ts`, `auth.functions.ts`, `useMe.ts`;
  `web/src/components/AuthForm.tsx`; `web/src/routes/_app/dashboard.tsx`,
  `healthz.ts`, `readyz.ts`; `web/package.json`, `web/Dockerfile` as needed.
- Removed: `api/`, `web/src/lib/api.ts`, `web/src/lib/api-types.ts`.
- `docker-compose.yml`, `.env.example`, `.gitignore`, `AGENTS.md`,
  `docs/technical-design.md`, `docs/database-design.md`.

## Data / contracts

- **Ids and time:** uuid primary keys with `gen_random_uuid()` for app tables;
  Better Auth tables keep its text ids. Timestamps are `timestamptz` defaulting
  to `now()`.
- **`user`:** `id`, `auth_subject` (unique, the Better Auth user id), `email`
  (unique, lowercase), `display_name` null, `locale` default `en`, `timezone`
  default `Africa/Nairobi`, `status` default `active` with check
  (`active`, `suspended`, `deleted`), `created_at`, `updated_at`.
- **Staff:** `role(id, name unique)`, `role_permission(role_id, permission)`
  primary key on both, `staff_member(user_id pk, role_id, mfa_enforced default
  true, created_at)`, `audit_log(id, staff_id, action, target_type, target_id
  null, before jsonb null, after jsonb null, reason, ip null, at)` with a check
  that `trim(reason)` is not empty and the `audit_log_immutable()` trigger
  blocking UPDATE and DELETE.
- **Permission matrix (frozen):** `support`: overview.read, users.read,
  tickets.read, tickets.reply. `finance`: overview.read, users.read, billing.read,
  billing.refund, pricing.write. `admin`: every permission except billing.refund
  and pricing.write. `owner`: all thirteen (overview.read, users.read,
  users.write, billing.read, billing.refund, pricing.write, tickets.read,
  tickets.reply, jobs.write, ai.write, flags.write, ops.write, audit.read).
- **Error shape:** `{ code, message }` with codes `unauthorized`, `forbidden`,
  `not_found`, `conflict`, `reason_required`, `unavailable`, `internal_error`.
  HTTP routes (`/readyz`) return it as `{ error: { code, message } }`; server
  functions return it as `{ ok: false, code, message }`.
- **`getMe` result:** `{ ok: true, me: { id, email, displayName, locale,
  timezone, staff: { role, permissions } | null } }`.
- **Env:** `DATABASE_URL`, `TEST_DATABASE_URL`, `BETTER_AUTH_SECRET`,
  `BETTER_AUTH_URL`, optional `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
- **Trust boundary:** the client never supplies a user id. `requireUser` is the
  only source of the acting user, and tenant queries go through the ownership
  helpers.

## Testing

Vitest against a real Postgres database (`jobmigo_test`, same server as dev) with
migrations applied in global setup and table cleanup between tests. Commands run
in `web/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`.
Live checks (steps 2 and 5) use the running dev server and the built-in browser
with locally created test accounts only. No browser test harness is configured,
so no browser suite is claimed.

## Notes for the AI

- Port behaviour from the Python modules (still in `api/` until step 6) rather
  than redesigning it; read `api/app/identity/service.py`,
  `api/app/admin/service.py` and `api/tests/` when writing each TS equivalent.
- Do not add Zod, pg-boss, Resend or any worker code in this feature.
- Better Auth, Drizzle and TanStack Start APIs change quickly: check the installed
  package types and docs before relying on a signature.
- Resetting the dev database deletes local data only; the test account from
  earlier work is expected to disappear.
- The review findings carried from feature 1 are resolved here as follows: F-01
  (step 5), F-02 (step 1), F-03 (disappears with JWKS), F-04 (step 2 disables
  account linking; Google linking itself stays untested). Mark them in the ledger
  as fixed only after their checks pass.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":14820,"specSha256":"7378a0e3ba0255bf82d8067ff3080accae61fc911a4b0ae142937e62f11bcc1f","branch":"refs/heads/feature/typescript-full-stack-switch","head":"5d5978edd4bd053a1ece0ec32932052ff535251d","baseRef":"refs/heads/main","baseCommit":"637ca97d70506a59a88a0214b74380c68aba59a2","sourceTree":"135603b858221edd9074b054b3fddcf75b989b99","landing":"local-merge","absentOptional":[]} -->

## Findings

### 27/F-01 [P2] closed - API token and `me` query cache survive a change of user in the same tab

**File:** web/src/lib/api.ts:21 (cache), web/src/components/AuthForm.tsx:105 (no reset on sign-in or sign-up)
**Found:** 2026-11-06 by /audit (scope: current; lens: security)
**Why it matters:** The module-level token cache and the TanStack Query cache are cleared only by the in-app `signOut` in `_app.tsx`. If the session ends elsewhere (sign-out in another tab, expiry, cleared cookie) and a different person then signs in on the same still-open tab, `apiFetch` keeps sending the previous user's JWT for up to about 14 minutes and the `['me']` query can still show the previous user's data. Reachable on a shared device. Impact is bounded to the 15 minute token lifetime.
**Suggested fix:** Call `clearApiToken()` and `queryClient.clear()` after a successful `signIn.email`, `signUp.email` and social sign-in return, before navigating to `/dashboard`.
**Resolution:** Closed 2026-11-07 by independent review: `AuthForm.tsx` calls `queryClient.clear()` after a successful email sign-in and sign-up before navigating, sign-out still clears the cache, and the API token cache (`api.ts`) is deleted. Original defect gone; no new defect in the repair.

### 27/F-02 [P3] closed - Test fixture downgrades to base on whatever `TEST_DATABASE_URL` names

**File:** api/tests/conftest.py:29
**Found:** 2026-11-06 by /audit (scope: current; lens: tests)
**Why it matters:** The session fixture runs `alembic downgrade base` then `upgrade head` against `TEST_DATABASE_URL`. If that variable is ever set to the dev database, the suite drops every table, including real users and the audit log.
**Suggested fix:** Assert the database name ends in `_test` (or differs from `DATABASE_URL`) before migrating, and fail loudly otherwise.
**Resolution:** Closed 2026-11-07 by independent review: `web/tests/global-setup.ts` throws unless `TEST_DATABASE_URL` is set and its database name ends in `_test` before any drop/migrate, and tests receive that URL as `DATABASE_URL` via `vitest.config.ts`. Original defect gone.

### 27/F-03 [P3] closed - Unreachable JWKS endpoint is reported to the client as a 401

**File:** api/app/identity/better_auth.py:45
**Found:** 2026-11-06 by /audit (scope: current; lens: quality)
**Why it matters:** `PyJWKClientConnectionError` is a `PyJWTError`, so a web server outage or timeout while fetching keys becomes `AuthError` and a 401 "Your session is not valid. Sign in again." The web app then sends users to `/sign-in` for what is an availability problem. No test covers the real `PyJWKClient` path.
**Suggested fix:** Catch `PyJWKClientConnectionError` separately and raise a 503 `unavailable` domain error; add one test with a failing key resolver.
**Resolution:** Closed 2026-11-07 by independent review: `api/` is deleted, no JWKS route or token verification remains (`/api/auth/*` is Better Auth only), and a test asserts no `auth_jwks` table.

## Independent review

**Status:** passed
**Target commit:** 5d5978edd4bd053a1ece0ec32932052ff535251d
**Base commit:** 637ca97d70506a59a88a0214b74380c68aba59a2
**Base ref:** main
**Spec hash:** 7378a0e3ba0255bf82d8067ff3080accae61fc911a4b0ae142937e62f11bcc1f
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-06T22:26:08Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-06T22:28:30Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD; git merge-base main HEAD; git status --short`: pass (HEAD equals target, merge base equals base, only review.md dirty)
- `shasum -a 256 blueprint/context/current-feature.md`: pass (matches Spec hash)
- `git diff --stat 637ca97..5d5978e` and full read of web/src/server, web/src/lib, web/src/start.ts, routes, drizzle/0000_baseline.sql, tests, compose, env, docs: pass
- `npm run lint` in web/: pass
- `npm run typecheck` in web/: pass
- `npm run build` in web/: pass
- `npm test` in web/: pass (4 files, 39 tests, jobmigo_test only)
- Repo-wide search for FastAPI, Alembic, SQLAlchemy, uv, JWKS, 8001, VITE_API_URL, AUTH_DATABASE_URL outside history: pass (only the spec, a schema test asserting no auth_jwks, and generic Blueprint skill text)

## Evidence

- Trust boundary: `requireUser` and `requirePermission` take the user only from `auth.api.getSession({ headers })`; `getMe` takes no input; no client-supplied user id reaches a query (identity.ts, permissions.ts, auth.functions.ts).
- `getMe` result omits `auth_subject`; tested (identity.test.ts). Unexpected errors map to a generic `internal_error` and log only the error class name.
- Baseline migration: seeded matrix matches `ROLE_PERMISSIONS` (tested against the database); `audit_log_immutable` row trigger and reason check are tested; `auth_jwks` absent.
- `accountLinking` disabled at web/src/lib/auth.ts:26; web/tests/global-setup.ts refuses a database name not ending in `_test`.
- api/ is fully removed from the tree, compose, .gitignore, AGENTS.md and docs; no leftover references found.
- Ledger: F-01, F-02, F-03 closed after re-examination; F-04 stays unverified; new F-05 to F-10 recorded in blueprint/context/findings.md.

## Findings

- F-05 [P2] open: `updateOwned` accepts `userId` and `id` in `values`.
- F-06 [P2] open: no test covers the session-header wiring, Better Auth config, request-id middleware or health routes.
- F-07 [P3] open: error and readiness logs carry no cause.
- F-08 [P3] open: `X-Request-Id` accepted without limits.
- F-09 [P3] open: audit trigger does not cover TRUNCATE.
- F-10 [P3] unverified: per-request insert and unbounded `listOwned`.
- F-04 [P2] unverified (carried over). No P0 or P1 finding is open or fixed.

## Remaining risk

- Google sign-in and account linking were never exercised (F-04); email verification is out of scope, so unverified email sign-up remains.
- Session handling relies on Better Auth defaults (cookie flags, rate limits); no automated test runs the real auth stack against the database (F-06).
- No browser test harness exists, so the web client switch was not re-verified by this review; the browser steps in the spec were not independently re-run.
- Dependency vulnerability scanning was not run (no network tools).
- Check was not required and was not run.
