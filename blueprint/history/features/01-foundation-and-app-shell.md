# Feature: Foundation and app shell

**From build-plan:** feature 1
**Build attempt:** 1
**Branch:** feature/foundation-and-app-shell
**Status:** verified

## Goal

A signed-in user lands in a themed Jobmigo app shell, and the API knows who they
are. Sign-up and sign-in run through Better Auth (in the web server) behind an
auth interface, every API request is authenticated and attributable to one user,
and the database has the tables that identify users and staff and record staff
actions. Every later feature builds on this.

## Design reference

Approved design canvas: https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q (screens
Sign up and Dashboard; sidebar from any app screen). Tokens are already ported
from `prototypes/theme.css` into `web/src/styles.css`. The Migo logo SVG and the
nav items come from the design. `prototypes/` stays until the first full UI
feature completes.

## In scope

**API (`api/`)**
- Tables and migrations: `user`, `role`, `role_permission`, `staff_member`, `audit_log` (append-only), seeded roles; and the Better Auth tables `auth_user`, `auth_session`, `auth_account`, `auth_verification`, `auth_jwks` (owned by Alembic, used by the web server).
- `AuthProvider` interface with a Better Auth implementation that verifies the JWTs Better Auth issues (EdDSA, keys from its JWKS endpoint, `iss` and `aud` checked, `sub`, `email` and `name` read from claims).
- `get_current_user` dependency: verifies the bearer token, creates the `user` row on first sight, rejects suspended users.
- `GET /v1/me`: the signed-in user, plus their staff role and permissions when they have one.
- Owner-scoping helper for tenant queries and a `require_permission` dependency for staff routes.
- `AuditService.record` for staff actions.
- Request id middleware and structured JSON logs; consistent error shape for 401, 403 and 404.
- Test setup that runs the real migrations against a dedicated test database.

**Web (`web/`)**
- Better Auth server instance inside TanStack Start (email and password; Google sign-in when its credentials are set), the JWT plugin, the auth route handler, an auth client, a server function that reads the session.
- Sign-in and sign-up pages built from the design with the Jobmigo tokens, with validation and error feedback.
- A typed API client: bearer token on every call, the API error shape parsed, types generated from the API's OpenAPI schema.
- TanStack Query provider and a `useMe` query.
- Authenticated layout: sidebar (logo, nav, user menu with sign out) and content area, responsive as in the design.
- `/` redirects signed-in users to `/dashboard` and shows a minimal public page otherwise.
- `/dashboard` placeholder that proves the round trip (greets the user from `/v1/me`) with loading, error and retry states.
- Environment variables and `.env.example` entries.

## Out of scope

- The real dashboard, jobs, applications and every other page (later features). Their nav items render disabled.
- The public homepage, waitlist and the onboarding flow (feature 19).
- Email verification and password reset (they need the email service, feature 24). Sign-up works without verification until then.
- Two-factor authentication and MFA enforcement for staff (feature 25).
- Entitlements, plans, credits (features 2 and 16). No `plan` column on `user`.
- Country, currency, Telegram id on `user` (features 16, 23, 10).
- Consent records and data export or deletion (feature 17).
- Staff provisioning UI and the `/admin` area (feature 25). Only the tables and checks exist.
- A restricted database role for the web server (done with the deployment setup).
- Postgres Row Level Security (arrives with the first tenant table in feature 3).
- Email sending, Telegram, AI gateway.

## Build loop

Per `blueprint/config.json`: `workflow.stepReview` is `feature` and
`workflow.checkpointCommits` is `disabled`. Build all steps on the feature
branch, review once at the end of the feature, and make no checkpoint commits.
`/complete` creates the final commit.

## Build steps

- [x] **1. Database tables and migration.**
  Models and one Alembic revision for `user`, `role`, `role_permission`, `staff_member` and `audit_log`; roles seeded; trigger rejects `UPDATE` and `DELETE` on `audit_log`; test fixtures create `jobmigo_test`, run migrations and roll back per test.
  *Done when:* upgrade and downgrade both succeed; tests show the audit trigger and the seeded roles; `uv run pytest`, `ruff check`, `mypy app` pass.

- [x] **2. Error shape and request logging.**
  `UnauthorizedError`, request id middleware, JSON logs without tokens, emails or bodies, one error shape for 401, 403, 404, 422 and 500.
  *Done when:* tests show the error shape and `X-Request-Id` header, hidden 500 internals, and that logs carry the request id but never the bearer token.

- [x] **3. Auth interface and Better Auth provider.**
  `AuthProvider.verify(token) -> Identity(subject, email, display_name)`. `BetterAuthProvider` verifies EdDSA signatures against the JWKS, `exp`, `iss`, `aud`, `sub` and a non-empty `email`. Settings `BETTER_AUTH_JWKS_URL` and `BETTER_AUTH_ISSUER`. A missing configuration gives a 503, not a crash.
  *Done when:* tests with locally generated Ed25519 keys and a JWKS-shaped key set accept a valid token and reject expired, wrong issuer, wrong audience, bad signature, no subject, no or blank email, malformed, empty, and non-EdDSA tokens. No test touches the network.

- [x] **4. Current user dependency and `/v1/me`.**
  `get_current_user` verifies the bearer token, finds the user by `auth_subject` or creates it from the token claims (defaults `locale` `en`, `timezone` `Africa/Nairobi`, `status` `active`), and returns it. Concurrent first requests create one row. Suspended or deleted users get 403. An email already owned by another identity gives 409. `GET /v1/me` returns the user and a `staff` object or `null`.
  *Done when:* tests cover missing and bad credentials, first creation and reuse, concurrent first requests, suspended user, staff and non-staff responses, the email conflict, and that `auth_subject` is never returned.

- [x] **5. Owner scoping and staff permissions.**
  `owner_scoped` and `OwnedRepository`, `require_permission`, `record_audit` with a required reason.
  *Done when:* tests show one user cannot read, update or delete another's rows through the helper, staff routes return 403 for non-staff, the wrong role and suspended staff and 200 for the right role, and the audit recorder rejects an empty reason.

- [x] **6. Better Auth tables migration.**
  In a scratch run, use `npx @better-auth/cli generate` (or the documented schema) with the planned config to see the exact tables and columns, then write one Alembic revision creating `auth_user`, `auth_session`, `auth_account`, `auth_verification` and `auth_jwks` to match, with the same column names and types Better Auth expects and indexes on lookup columns. Add `modelName` mappings to the Better Auth config in step 7 so it uses these table names.
  *Done when:* `alembic upgrade head` and `downgrade base` succeed; a test confirms each table and its columns exist; the schema matches what the Better Auth CLI reports as required (no missing tables or columns).

- [x] **7. Better Auth in the web server.**
  Install `better-auth`, `pg` and its types, and `openapi-typescript` (dev). Add `src/lib/auth.ts`: `betterAuth` with a `pg` pool on `AUTH_DATABASE_URL`, `baseURL` and secret from env, the four `modelName` mappings, `emailAndPassword` enabled (minimum password length 8, no verification yet), Google provider only when both Google variables are set, the `jwt` plugin with `definePayload` returning `id`, `email`, `name` and `emailVerified`, and `tanstackStartCookies()` last. Add `src/routes/api/auth/$.ts`, `src/lib/auth-client.ts` (with the JWT client plugin), and `src/lib/auth.functions.ts` (`getSession`). Add env handling.
  *Done when:* `npm run build` and `npm run lint` pass; with the database and web server running, a sign-up request to `/api/auth/sign-up/email` succeeds, `/api/auth/jwks` serves an Ed25519 key, a token from `/api/auth/token` is accepted by the API at `GET /v1/me` (live check run during implementation, using no external accounts), and a request with a wrong password is rejected.

- [x] **8. Sign-in and sign-up pages and the API client.**
  Add `/sign-in` and `/sign-up` from the design: email, password (min 8), a Google button shown only when Google is configured, labelled fields, inline error messages tied to fields with `aria-describedby`, an `aria-live` region for form-level errors (wrong credentials, email already used), focus moved to the first error, 44px controls, loading state on submit, and a link between the two pages. Add `src/lib/api.ts` (bearer token from `authClient.token()`, cached until shortly before expiry; parses the error shape into `ApiError`; nothing sensitive in console output), `npm run api:types` writing `src/lib/api-types.ts`, and the TanStack Query provider.
  *Done when:* `npm run lint` and `npm run build` pass; in a browser, an invalid email, a short password, a duplicate email and a wrong password each show the right message, and a valid sign-up lands on `/dashboard`.

- [x] **9. App shell and dashboard placeholder.**
  Authenticated layout route that redirects signed-out visitors to `/sign-in`. Sidebar (Migo logo and wordmark, nav items from the design: Dashboard, Jobs, Applications, Outreach, Documents, Career profile, Settings, with only Dashboard as a link and the rest `aria-disabled` with a "Soon" label, user menu with sign out). Below the tablet breakpoint the sidebar stacks above the content. `/dashboard` greets the user by name from `useMe` with a Migo empty state, a skeleton while loading, an error card with Retry on failure (a 401 sends the user to `/sign-in`), and a route-level error boundary. `/` redirects signed-in users to `/dashboard` and otherwise shows a minimal Jobmigo page with Sign in and Get started links. Interactive controls are at least 44px, focus is visible, motion respects reduced-motion.
  *Done when:* `npm run lint` and `npm run build` pass; in a browser with the API running, a signed-in user sees the shell and their name on `/dashboard`, a signed-out visit lands on `/sign-in`, stopping the API shows the error card and Retry recovers, sign out returns to `/sign-in`, and the layout works at 390px and 1280px widths.

- [x] **10. Environment, compose and docs.**
  Update `.env.example` and `docker-compose.yml` (api and web), document `api:types`, the test database and the new variables in `AGENTS.md` Commands. No scope additions.
  *Done when:* a fresh clone can follow `AGENTS.md` and `.env.example` to run db, api and web; `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app`, `uv run pytest`, `npm run lint` and `npm run build` all pass.

## Files / areas

- `api/app/platform/` - `config.py`, `db.py`, `errors.py`, `logging.py`, `request_id.py`, `ownership.py`, `health.py`.
- `api/app/identity/` - `models.py`, `auth.py` (interface, Identity), `better_auth.py`, `service.py`, `dependencies.py`, `routes.py`, `schemas.py`.
- `api/app/admin/` - `permissions.py`, `models.py`, `service.py`, `dependencies.py`, `audit.py`.
- `api/migrations/versions/` - the identity and staff revision, and the Better Auth tables revision.
- `api/tests/` - `conftest.py`, one module per area.
- `web/src/lib/` - `auth.ts` (server only), `auth-client.ts`, `auth.functions.ts`, `api.ts`, `api-types.ts` (generated), `query.ts`.
- `web/src/routes/` - `__root.tsx`, `index.tsx`, `sign-in.tsx`, `sign-up.tsx`, `api/auth/$.ts`, `_app.tsx`, `_app/dashboard.tsx`.
- `web/src/components/` - `Logo`, `Migo`, `Sidebar`, `UserMenu`, `AuthForm` pieces, `ErrorCard`, `Skeleton`.
- `web/package.json`, `web/package-lock.json`, `.env.example`, `docker-compose.yml`, `AGENTS.md`.

## Data / contracts

**Application tables** (PostgreSQL, UUID keys generated by the database, timestamps `timestamptz`, naming convention from `db.py`):

- `user`: `id` uuid PK, `auth_subject` text unique not null (the Better Auth user id), `email` text unique not null (lowercase), `display_name` text null, `locale` text default `en`, `timezone` text default `Africa/Nairobi`, `status` text default `active` (check: `active`, `suspended`, `deleted`), `created_at`, `updated_at`.
- `role`, `role_permission`, `staff_member` (`user_id` PK and FK, `role_id` FK, `mfa_enforced` default true), `audit_log` (append-only, `reason` required) as built in steps 1 to 5.
- Tenant tables added later carry `user_id` uuid FK to `user.id`.

**Better Auth tables** (Alembic owns the schema, the web server reads and writes them): `auth_user`, `auth_session`, `auth_account`, `auth_verification`, `auth_jwks`, with the columns Better Auth requires. They are separate from the application `user` table. The API never reads them; it relies on the JWT.

**Token contract:** a short-lived (15 minutes by default) EdDSA JWT from the Better Auth jwt plugin, `iss` and `aud` equal to the web base URL, `sub` the Better Auth user id, plus `email`, `name` and `emailVerified` claims. The API verifies it against the JWKS at `BETTER_AUTH_JWKS_URL` and trusts nothing else from the client.

**`GET /v1/me`** (requires bearer token): `id`, `email`, `display_name`, `locale`, `timezone`, `staff` (`null` or `{role, permissions}`). `auth_subject` is never returned.

**Errors** (all non-2xx): `{"error": {"code": "unauthorized | forbidden | not_found | conflict | validation_error | unavailable | internal_error", "message": "string"}}`. 401 carries `WWW-Authenticate: Bearer`. 500 never exposes internals.

**Environment variables**
- API: `DATABASE_URL`, `TEST_DATABASE_URL`, `WEB_ORIGIN`, `BETTER_AUTH_JWKS_URL`, `BETTER_AUTH_ISSUER`.
- Web: `AUTH_DATABASE_URL` (plain `postgresql://` form for the `pg` driver, separate from the API's `postgresql+asyncpg://` URL), `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `VITE_API_URL`, optional `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

## Testing

- API logic tests with pytest (`uv run pytest`): migrations and triggers, error shape, token verification cases, user creation and concurrency, owner scoping, permission checks, audit reason rule, auth table existence. Tests need the Postgres container and never the network.
- Web: `npm run lint` and `npm run build`. No web unit-test runner or Browser tests command exists, so none is added here.
- Live checks during implementation (no external accounts needed): sign-up and token round trip against the running web server and API (step 7), then the browser checks in steps 8 and 9, reporting what was and was not seen. Google sign-in cannot be verified without Google credentials and is reported as not exercised.
- Final gate: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app`, `uv run pytest`, `npm run lint`, `npm run build`.

## Notes for the AI

- Better Auth runs in the web server; the API stays the system of record for application data. Nothing outside `identity/better_auth.py` knows Better Auth's token details, so a provider change stays contained.
- Follow `blueprint/context/coding-standards.md`: routes thin, services own rules, repositories owner-scoped, typed domain errors, no personal text in logs.
- Never trust a client-supplied user id. Never log tokens, emails or bodies. Never return `auth_subject`.
- Alembic is the only schema owner. Do not run Better Auth's own migrate command against the real database; use the CLI only to inspect what it expects.
- The web server needs a database connection for Better Auth. A role limited to the `auth_*` tables comes with the deployment setup; for now it uses the same local database credentials.
- Row Level Security and the `app.user_id` session setting are deferred to the first tenant table.
- Replace the starter `src/routes/index.tsx`; keep `__root.tsx` head links and the reduced-motion rule.
- Use the design canvas for visual detail (sidebar width 264px, active nav in accent-soft, card radius 20px). Do not add dark mode or pages beyond the list above.
- Ports: web 3000, api 8001, Postgres 5442.

## Open questions

- None. The staff permission matrix default (support, finance, admin, owner) was confirmed with the spec and is implemented in `admin/permissions.py`.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":16304,"specSha256":"ec8693997aaa084f9e0fe446c250a8125beca5037e51cb7cf77afe91bc04971f","branch":"refs/heads/feature/foundation-and-app-shell","head":"cd6d2033a4406e66abd9f660ba3ebd387104557e","baseRef":"refs/heads/main","baseCommit":"f9207c34a963b602ff9ddc66cf915c93d7760b95","sourceTree":"c80175690e11578adeaefb20406f56fa8f532527","landing":"local-merge","absentOptional":[]} -->

## Independent review

**Status:** passed
**Target commit:** cd6d2033a4406e66abd9f660ba3ebd387104557e
**Base commit:** f9207c34a963b602ff9ddc66cf915c93d7760b95
**Base ref:** main
**Spec hash:** ec8693997aaa084f9e0fe446c250a8125beca5037e51cb7cf77afe91bc04971f
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-06T18:44:00Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-06T19:10:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD; git merge-base main HEAD; git status --porcelain; shasum -a 256 blueprint/context/current-feature.md`: pass (HEAD, base and spec hash match the request; only review.md dirty)
- `git diff --stat f9207c3..cd6d203`: pass (62 files reviewed)
- `uv run pytest -q` (api/): pass (42 passed)
- `uv run ruff check .` (api/): pass
- `uv run ruff format --check .` (api/): pass
- `uv run mypy app` (api/): pass
- `npm run lint` (web/): pass
- `npm run build` (web/): not run (Check not required; lint only)

## Evidence

- Freshness verified: HEAD equals target, main merge-base equals base commit, spec hash matches, no dirty path other than review.md.
- Read in full: api/app/identity/*, api/app/admin/*, api/app/platform/{errors,logging,ownership,request_id,config,db}.py, api/app/main.py, both migrations, api/tests/conftest.py, web/src/lib/{auth,auth-client,auth.functions,api,useMe}.ts, web/src/routes/{_app,index,sign-in,_app/dashboard,__root,api/auth/$}.tsx, web/src/components/AuthForm.tsx.
- JWT verification pins EdDSA, requires exp, sub, iss and aud, rejects blank email; PyJWKClient has a forced-refresh cooldown, so unknown-kid tokens do not amplify JWKS fetches.
- get_or_create_user handles concurrent first requests via ON CONFLICT DO NOTHING and maps an email clash to 409; auth_subject is not in MeResponse; suspended and deleted users get 403.
- owner_scoped covers select, update and delete; audit_log has a trigger blocking UPDATE and DELETE and a non-empty reason check; no skipped or focused tests found.

## Findings

- F-01 [P2] open: token and query cache survive a user change in the same tab
- F-02 [P3] open: test fixture downgrades whatever TEST_DATABASE_URL names
- F-03 [P3] open: JWKS outage reported as 401 instead of 503
- F-04 [P2] unverified: unverified-email pre-hijack with future Google linking
- No P0 or P1 finding.

## Remaining risk

- Web build, browser flows and the live sign-up/token round trip were not re-run by this reviewer (Check not required); web has no unit tests.
- Google sign-in and Better Auth account-linking behavior were not exercised (F-04).
- audit_log trigger does not cover TRUNCATE; staff MFA (mfa_enforced) is stored but not enforced yet (out of scope for this feature).
- No dependency vulnerability scan was run.
