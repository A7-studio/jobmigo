# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to land while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-04 [P2] unverified - Pre-registered unverified email plus Google sign-in could allow account pre-hijack

**File:** web/src/lib/auth.ts:26
**Found:** 2026-11-06 by /audit (scope: current; lens: security)
**Why it matters:** Email and password sign-up needs no verification (an accepted out-of-scope item until feature 24). If Google is enabled later and Better Auth links a verified Google identity to an existing unverified email-password user, whoever pre-registered that address keeps the password. Not exercised: Google is not configured and the linking behavior of the installed Better Auth version was not tested.
**Suggested fix:** Before enabling Google, or with feature 24, require email verification before sign-in, or disable implicit account linking for unverified users; confirm with a test.
**Resolution:** Feature 27 disables `account.accountLinking` in `src/lib/auth.ts:26`. Re-examined 2026-11-07 by independent review: the setting is present, but no test or live check exercises Google linking and the config is untested (see F-07). Stays unverified until Google is configured.

### F-05 [P2] open - `updateOwned` lets the caller overwrite `userId` and `id`

**File:** web/src/server/ownership.ts:53
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** `values` is `Partial<T['$inferInsert']>`, which includes `userId` and `id`. A later handler that passes a parsed request body straight through (the usual shape) lets a client reassign a row to another user or change its key, defeating the "client never supplies a user id" boundary the helper exists to enforce. No caller exists yet and no test covers it.
**Suggested fix:** Type `values` as `Omit<Partial<T['$inferInsert']>, 'id' | 'userId'>` and strip those keys at runtime; add a test that `userId` in `values` is ignored or rejected. Nothing is lost.
**Resolution:**

### F-06 [P2] open - Auth wiring behind `requireUser`, `getMe` and `requirePermission` has no test

**File:** web/src/server/identity.ts:57, web/src/server/permissions.ts:63, web/src/lib/auth.functions.ts:21
**Found:** 2026-11-07 by /audit (scope: current; lens: tests)
**Why it matters:** Every test injects a session object into `resolveUser`, `buildMe` or `assertPermission`. Nothing exercises `requireUser(headers)`, `requirePermission(headers, ...)`, the `getMe` server function, the Better Auth Drizzle adapter config (model names, `accountLinking: false`, no JWT), the request-id middleware (`start.ts`) or `/healthz` and `/readyz` (503 path). These carry the session-to-user trust boundary and were verified only by a one-off live check. A broken model-name mapping or a changed Better Auth default would pass the suite.
**Suggested fix:** Add one Vitest file that imports `auth` against the test database, signs up and signs in through `auth.api`, and asserts `requireUser(headers)` returns that user, a request with no cookie raises `UnauthorizedError`, and account linking is off. Add a small test for the `/readyz` handler failure shape and the middleware header.
**Resolution:**

### F-07 [P3] open - Unexpected errors and readiness failures are logged without a cause

**File:** web/src/server/errors.ts:48, web/src/routes/readyz.ts:14
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** `toResult` logs only the error class name, and `/readyz` swallows the exception with no log at all. A 500 `internal_error` or a failing readiness probe cannot be diagnosed from logs. The no-leak behaviour is correct for the client; the server log is too thin.
**Suggested fix:** Log `error.message` code-side-safe fields (for example the Postgres `code`) and a short stack, never request bodies, and log the readyz failure once at `warn`. Keep the client messages unchanged.
**Resolution:**

### F-08 [P3] open - `X-Request-Id` is trusted without length or character limits

**File:** web/src/start.ts:6
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** Any client value is echoed in the response header and written to every log line for that request. JSON encoding prevents log forging, but a very long or misleading id inflates logs and can be used to confuse tracing.
**Suggested fix:** Accept the header only when it matches a short pattern (for example `^[A-Za-z0-9._-]{1,64}$`), otherwise generate a UUID.
**Resolution:**

### F-09 [P3] open - Audit immutability trigger does not cover TRUNCATE

**File:** web/drizzle/0000_baseline.sql:132
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** `BEFORE UPDATE OR DELETE ... FOR EACH ROW` blocks row changes but `TRUNCATE audit_log` succeeds. Only a role with table privileges can run it, and the app uses one owner role, so the exposure is limited to app bugs or raw SQL.
**Suggested fix:** Add a statement-level `BEFORE TRUNCATE` trigger using the same function in a new migration, with a test.
**Resolution:**

### F-10 [P3] unverified - Per-request write and unbounded list helper may cost more than needed

**File:** web/src/server/identity.ts:30, web/src/server/ownership.ts:44
**Found:** 2026-11-07 by /audit (scope: current; lens: performance)
**Why it matters:** `resolveUser` runs an `INSERT ... ON CONFLICT DO NOTHING` on every authenticated request before selecting, and `getMe` then runs two more staff queries. `listOwned` has no limit, so a future caller on a large table returns every row. No profiling was done and there are no callers of `listOwned` yet, so this is a lead, not a defect.
**Suggested fix:** Select first and insert only on a miss (keep the conflict handling), and require a limit argument in `listOwned` when the first list feature lands.
**Resolution:**
