# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to land while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-01 [P2] open - API token and `me` query cache survive a change of user in the same tab

**File:** web/src/lib/api.ts:21 (cache), web/src/components/AuthForm.tsx:105 (no reset on sign-in or sign-up)
**Found:** 2026-11-06 by /audit (scope: current; lens: security)
**Why it matters:** The module-level token cache and the TanStack Query cache are cleared only by the in-app `signOut` in `_app.tsx`. If the session ends elsewhere (sign-out in another tab, expiry, cleared cookie) and a different person then signs in on the same still-open tab, `apiFetch` keeps sending the previous user's JWT for up to about 14 minutes and the `['me']` query can still show the previous user's data. Reachable on a shared device. Impact is bounded to the 15 minute token lifetime.
**Suggested fix:** Call `clearApiToken()` and `queryClient.clear()` after a successful `signIn.email`, `signUp.email` and social sign-in return, before navigating to `/dashboard`.
**Resolution:**

### F-02 [P3] open - Test fixture downgrades to base on whatever `TEST_DATABASE_URL` names

**File:** api/tests/conftest.py:29
**Found:** 2026-11-06 by /audit (scope: current; lens: tests)
**Why it matters:** The session fixture runs `alembic downgrade base` then `upgrade head` against `TEST_DATABASE_URL`. If that variable is ever set to the dev database, the suite drops every table, including real users and the audit log.
**Suggested fix:** Assert the database name ends in `_test` (or differs from `DATABASE_URL`) before migrating, and fail loudly otherwise.
**Resolution:**

### F-03 [P3] open - Unreachable JWKS endpoint is reported to the client as a 401

**File:** api/app/identity/better_auth.py:45
**Found:** 2026-11-06 by /audit (scope: current; lens: quality)
**Why it matters:** `PyJWKClientConnectionError` is a `PyJWTError`, so a web server outage or timeout while fetching keys becomes `AuthError` and a 401 "Your session is not valid. Sign in again." The web app then sends users to `/sign-in` for what is an availability problem. No test covers the real `PyJWKClient` path.
**Suggested fix:** Catch `PyJWKClientConnectionError` separately and raise a 503 `unavailable` domain error; add one test with a failing key resolver.
**Resolution:**

### F-04 [P2] unverified - Pre-registered unverified email plus Google sign-in could allow account pre-hijack

**File:** web/src/lib/auth.ts:26
**Found:** 2026-11-06 by /audit (scope: current; lens: security)
**Why it matters:** Email and password sign-up needs no verification (an accepted out-of-scope item until feature 24). If Google is enabled later and Better Auth links a verified Google identity to an existing unverified email-password user, whoever pre-registered that address keeps the password. Not exercised: Google is not configured and the linking behavior of the installed Better Auth version was not tested.
**Suggested fix:** Before enabling Google, or with feature 24, require email verification before sign-in, or disable implicit account linking for unverified users; confirm with a test.
**Resolution:**
