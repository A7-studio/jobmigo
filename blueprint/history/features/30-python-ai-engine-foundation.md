# Feature: Python AI engine foundation

**From build-plan:** feature 30
**Build attempt:** 1
**Branch:** feature/python-ai-engine-foundation
**Status:** verified

## Goal

A second service exists: a Python FastAPI "engine" in `engine/` that the TanStack Start
server can call over internal HTTP. It starts, reports health, accepts only calls that carry the
shared token and a user id, owns its own Postgres schema through Alembic migrations, runs
in Docker as a non-root user, and has its own lint, type-check and test commands. A small
TypeScript client in the web server makes calls with the token and the verified user id. It
contains no AI, storage or product logic yet; those arrive in features 31 and 3. The point is a
correct, tested seam and the conventions every later engine feature will follow.

## In scope

- **Python project** in `engine/` managed with `uv`: Python 3.13, FastAPI, Uvicorn, Pydantic v2,
  SQLAlchemy 2 (async) with asyncpg, Alembic; dev tools pytest,
  pytest-asyncio, httpx, Ruff (lint and format) and mypy in strict mode. Versions are pinned in
  `uv.lock`.
- **App factory and settings** (`engine/src/engine/`): settings read from the environment
  (`ENGINE_TOKEN`, `DATABASE_URL`, optional `LOG_LEVEL`); the app refuses to
  start without an `ENGINE_TOKEN` of at least 32 characters, naming the variable and never
  its value.
- **Endpoints:** `GET /healthz` (process is up, no auth) and `GET /readyz` (database reachable,
  no auth, reveals no detail); `GET /internal/whoami` (requires auth) returning `{ "userId": ... }`
  as the minimal proof of the boundary. No other endpoints.
- **Internal auth:** every `/internal/*` route requires `Authorization: Bearer <ENGINE_TOKEN>`
  (constant-time compare) and an `X-User-Id` header holding a UUID. A missing or wrong token
  is 401 `unauthorized`; a missing or malformed user id is 400 `invalid_request`. The engine
  trusts the user id because only the web server can reach it; it has no cookies and no sessions.
- **Stable error shape:** every error, including validation errors and unexpected failures, is
  `{ "code": ..., "message": ... }`, matching the web app's contract; unexpected errors are
  logged without request data and returned as `internal_error` (500).
- **Logging and request ids:** JSON log lines with the request id (taken from `X-Request-Id` or
  generated, echoed on the response); no tokens, user ids, headers, bodies or paths with ids.
- **Database and migrations:** an async engine on `DATABASE_URL`, objects in a dedicated
  schema `engine` (including Alembic's version table); the schema is created by the
  Alembic environment (its version table lives in it) and the one baseline revision is empty
  (feature 31 adds the first tables); migrations run from the container
  entrypoint, never on import.
- **Docker:** `engine/Dockerfile` (multi-stage, uv, non-root user, health check on
  `/healthz`, entrypoint runs `alembic upgrade head` then Uvicorn); an `engine` service in the dev
  `docker-compose.yml` (published on `127.0.0.1:8100` only) and an `engine` service in
  `deploy/docker-compose.prod.yml` with **no published port**, the token passed from
  `.env.production`, and the web service given `ENGINE_URL` and `ENGINE_TOKEN`.
- **TypeScript client** `web/src/server/engine/client.ts`: `callEngine(path, { userId, method,
  body })` that sends the token, the user id and the current request id, times out after 30 s,
  retries nothing, and maps failures to `DomainError`s (`engine_not_configured` 503,
  `engine_unavailable` 502, and the engine's own `{ code, message }` passed through). The user id
  argument comes from `requireUser`, never from client input.
- **Commands and docs:** the engine commands and a combined `Verify` in `AGENTS.md`;
  `.env.example` values; `docs/technical-design.md` and `docs/database-design.md` notes; a short
  `engine/README.md`.

## Out of scope

- The AI gateway, usage ledger, cache, CV storage and parsing, evaluation (features 31, 3 and
  later); any table in the `engine` schema beyond Alembic's own.
- Production rollout of the engine: deploy scripts, backups of the new schema beyond what
  one shared database already covers, `readyz` of the web app checking the engine, and
  `docs/deploy.md` changes beyond a note (done with the next deploy-readiness pass).
- A job queue or worker, tracing, metrics, rate limiting, and mutual TLS (the network boundary
  and token are the controls).
- CI configuration (there is none in the repo yet).

## Build loop

Per `blueprint/config.json`: `workflow.stepReview: feature` and
`workflow.checkpointCommits: disabled`. Build the steps in order on the branch above, run the
narrowest check while iterating, run Verify once after the last step, then the fresh independent
review (a new service, a trust boundary and secrets, so `when-sensitive` selects it).

## Build steps

- [x] 1. **Project skeleton and tooling.** `engine/pyproject.toml`, `uv.lock`, the `engine`
  package with an app factory, settings, JSON logging, request-id middleware, the stable error
  handlers and `GET /healthz`; Ruff, mypy strict and pytest configured. Done when
  `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest` passes in
  `engine/`, tests prove `/healthz` returns 200, a supplied `X-Request-Id` is echoed and a
  generated one appears otherwise, a missing or short `ENGINE_TOKEN` stops startup with a
  message that names the variable and not a value, an unknown route and an unexpected exception
  both return `{ code, message }`, and log output contains no token.
- [x] 2. **Internal auth and `whoami`.** The auth dependency and `GET /internal/whoami`. Done
  when tests prove: no header, a wrong token, a token of the wrong length and a token with the
  wrong scheme are all 401 `unauthorized` with the same body; a valid token with a missing,
  malformed or non-UUID `X-User-Id` is 400 `invalid_request`; a valid call returns the user id;
  comparison uses `hmac.compare_digest`; and the token never appears in any response or log
  line.
- [x] 3. **Database, Alembic and `readyz`.** Async engine and session factory, the `engine`
  schema, the baseline migration, `GET /readyz`. Tests run against a dedicated database
  (`ENGINE_TEST_DATABASE_URL`, name must end `_test`, created if missing) so they never touch the
  web app's test data. Done when `alembic upgrade head` creates schema `engine` with its version
  table and nothing in `public`, running it twice is a no-op, `downgrade base` returns to an
  empty version table, `/readyz` is 200 with the database up and 503 without detail when it is not, and the
  tests refuse a database whose name does not end in `_test`.
- [x] 4. **Docker and compose.** `engine/Dockerfile`, the dev compose service, the production
  compose service (no published port), `.env.example` and `.env.production.example` entries.
  Done when `docker build engine` succeeds, the container runs as a non-root user, applies the
  migration against the local database, answers `/healthz` and `/readyz`, and rejects
  `/internal/whoami` without the token; `docker compose -f deploy/docker-compose.prod.yml config`
  is valid and shows the engine with no ports; and nothing in the image holds the token.
- [x] 5. **TypeScript client.** `web/src/server/engine/client.ts`, the error classes, and
  tests with a fake `fetch`. Done when tests prove the headers sent (token, user id, request id),
  the 30 s timeout is wired through the abort signal, a 401 or 5xx from the engine and a network
  failure map to the stable errors without leaking the token or response body, the engine's
  `{ code, message }` is passed through for 4xx, a missing `ENGINE_URL` or `ENGINE_TOKEN` is
  `engine_not_configured` naming the variable only, and an optional live test (skipped unless
  `ENGINE_LIVE_TEST=1`) calls the running local engine's `whoami`.
- [x] 6. **Docs and final checks.** `AGENTS.md` commands and `Verify` for both services,
  `engine/README.md`, the technical-design and database-design notes. Done when the engine
  checks, `npm run lint && npm run typecheck && npm run build && npm test`, and
  `docker compose config` for both compose files all pass, and a manual check starts the engine
  container and runs the live client test successfully.
- [x] 7. **Repair review findings.** F-50 (the compose files tolerate an unset
  `ENGINE_TOKEN` so other commands keep working; `deploy.sh` refuses a token under 32
  characters and waits for both web and engine; `docs/deploy.md` adds the secret), F-51
  (auth is required by the `/internal` router itself, with a test that calls every internal
  route without a token), F-52 (the client checks the path as the URL parser reads it and
  refuses redirects), F-53 (request ids must match in full), F-54 (tests for the 422 and 405
  shapes, constant-time comparison, readiness timeout and no connection on startup), F-55
  (the unused `ENVIRONMENT` setting removed, an invalid `LOG_LEVEL` names the variable, `pydantic`
  and `starlette` declared, `Allow` kept on a 405). Done when the new tests pass and the full
  Verify passes.

## Files / areas

- New: `engine/` (`pyproject.toml`, `uv.lock`, `Dockerfile`, `alembic.ini`, `migrations/`,
  `src/engine/`, `tests/`, `README.md`), `web/src/server/engine/client.ts`,
  `web/tests/engine-client.test.ts`
- Changed: `docker-compose.yml`, `deploy/docker-compose.prod.yml`, `.env.example`,
  `deploy/.env.production.example`, `web/src/server/errors.ts`, `AGENTS.md`,
  `docs/technical-design.md`, `docs/database-design.md`, `.gitignore` (Python caches)
- Untouched: the AI gateway, existing routes and components, `deploy.sh`, `backup.sh`

## Data / contracts

- Environment: `ENGINE_TOKEN` (at least 32 characters; generate with `openssl rand -hex 32`),
  `ENGINE_URL` (web side, for example `http://localhost:8100` locally and `http://engine:8000` in
  the production network), `DATABASE_URL` (the same database as the web app),
  `ENGINE_TEST_DATABASE_URL` (tests), `LOG_LEVEL` (default `INFO`).
- Auth headers: `Authorization: Bearer <ENGINE_TOKEN>` and `X-User-Id: <uuid>`; optional
  `X-Request-Id`.
- `GET /healthz` returns 200 `{ "status": "ok" }`. `GET /readyz` returns 200 `{ "status": "ready" }`
  or 503 `{ "code": "not_ready", "message": "Not ready." }`.
- `GET /internal/whoami` returns 200 `{ "userId": "<uuid>" }`.
- Errors: `{ "code": string, "message": string }` with codes `unauthorized` (401),
  `invalid_request` (400 or 422), `not_found` (404), `not_ready` (503), `internal_error` (500).
- Schema: Postgres schema `engine`, Alembic version table `engine.alembic_version`, no
  cross-schema foreign keys. The engine connects as the same database role as the web app.
- Container: listens on 8000 inside the container; dev compose maps `127.0.0.1:8100:8000`;
  production publishes nothing.
- Client: `callEngine(path, { userId, method?, body?, signal? })` returns the parsed JSON or
  throws a `DomainError`; the user id must be a UUID string supplied by server code.

## Testing

pytest with `httpx.AsyncClient` over the ASGI app for endpoint tests, a dedicated
`jobmigo_engine_test` database for migration and readiness tests (the engine's test setup creates
it, like the web tests do for theirs), and Vitest with a fake `fetch` for the TypeScript client.
Docker and compose behaviour are verified by running the commands in step 4 and step 6, and the
live client test is opt-in. No browser tests.

## Notes for the AI

- The token and user ids are secrets-adjacent: never log them, never put them in error
  messages, and compare the token with `hmac.compare_digest`.
- Keep the engine small and typed: no `Any`, Pydantic models for every request and response,
  settings in one module, no import-time side effects (no database connection or migration on
  import).
- Mirror the web app's patterns where they apply: stable `{ code, message }` errors, JSON logs with
  a request id, no personal data in logs, tests that refuse to run against a non-test database.
- Do not add dependencies beyond the list in scope (stop and ask if a different library looks
  necessary). Do not add AI, storage or product tables or endpoints; feature 31 and feature 3 own
  them.
- Python is new to the founder: favour clear, idiomatic code and short docstrings that explain
  why, and put the commands in `engine/README.md`.
- Compose changes must not publish the engine in production; verify with `docker compose
  config`.
- The `uv` toolchain installs Python 3.13 itself; the system Python (3.9) is not used.

## Open questions

None that block the build. To confirm later: the first engine tables (feature 31) and whether
the web `readyz` should check the engine once the stack is deployed.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":12747,"specSha256":"88b518f881412079764b199e0a744d684bd8094963902c764d3253736d569f43","branch":"refs/heads/feature/python-ai-engine-foundation","head":"2c382f8c72ed892b38aecbe9c3584e0b41159380","baseRef":"refs/heads/main","baseCommit":"3297f4fe4c908e25d38e1053dabba62871316b1a","sourceTree":"335e52e41cec12967f0f291d50d507d8378fd7de","landing":"local-merge","absentOptional":[]} -->

## Findings

### 30/F-50 [P2] closed - Required `ENGINE_TOKEN` in both compose files breaks every compose command and the existing deploy, backup and restore flows until it is set

**File:** deploy/docker-compose.prod.yml:30, deploy/docker-compose.prod.yml:51, docker-compose.yml:25
**Found:** 2026-11-07 by /audit independent (scope: current; lens: security, quality)
**Why it matters:** `${ENGINE_TOKEN:?...}` is evaluated for the whole file, not per selected service. Verified with `docker compose config` and an empty or missing token: dev `docker compose config db` and prod `config` both fail with "required variable ENGINE_TOKEN is missing a value". (1) Dev: `.env.example` ships `ENGINE_TOKEN=` empty, and AGENTS.md says to copy it and run `docker compose up -d db`, which now fails until a token is generated. (2) Production: on an existing server whose `.env.production` has no token, `deploy.sh` (`up -d --build`), `backup.sh` and `restore.sh` (`exec ... db`), `ps` and `logs` all fail at interpolation. `deploy.sh` rolls back to the previous commit, so nothing is half-applied, but a backup run against a checkout that already has the new compose file stops silently. `deploy.sh` and `docs/deploy.md` do not mention the new secret, `deploy.sh` does not validate it (length of at least 32 is enforced only by the engine, which would crash-loop while `wait_healthy` checks only the web container and reports success), and the spec leaves them untouched. The `:?` message also appears in `docker compose` output only, never the value, which is fine.
**Suggested fix:** Add `ENGINE_TOKEN` to the pre-flight checks in `deploy.sh` (present and at least 32 characters, like the `POSTGRES_PASSWORD` check) and one line in `docs/deploy.md` (the spec's deploy note) in this feature or the very next deploy pass; make `.env.example` carry a clearly-labelled generation command and have the db-only commands in AGENTS.md note it, or use `${ENGINE_TOKEN:-}` in the dev compose for the web service and `:?` only where the engine needs it. Consider having `wait_healthy` also require the engine container healthy.
**Resolution:** Feature 30 repair step 7: both compose files use `${ENGINE_TOKEN:-}` so other commands work without it (the engine refuses to start without a valid token and shows it unhealthy); `deploy.sh` refuses a token under 32 characters and waits for both web and engine to be healthy; `docs/deploy.md` adds the secret. Checked: `deploy.sh --dry-run` refuses a missing or short token and passes with a good one; `docker compose config` works for both files with no token.

Closed 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests). Re-examined: scratch env files with `ENV_FILE` and `--dry-run` refuse a missing, empty, short and 31-character token and pass 32 characters; `set -u`, pipefail and the `|| true` in `get_var` behave; `wait_healthy` requires both web and engine and its `set -e` interaction is safe because it runs under `if start_stack`; the production compose renders the engine with no ports. Residual edge cases are new findings F-57 and F-58.

### 30/F-51 [P2] closed - Internal auth is attached per route, so a new `/internal/*` route without the dependency is silently unauthenticated

**File:** engine/src/engine/routes/internal.py:10, engine/src/engine/auth.py:42
**Found:** 2026-11-07 by /audit independent (scope: current; lens: security, quality)
**Why it matters:** The spec says every `/internal/*` route requires the token and a UUID user id, and every later engine feature will add routes here. The router has no dependency; only `whoami` takes `CurrentUser`. A route added later that forgets the parameter (or that does not need the user id) is open to anyone who can reach port 8100 or the internal network, and no test would notice. Today it is safe (one route, 401 verified live), so this is a guard against drift on the project's only trust boundary.
**Suggested fix:** Set `APIRouter(prefix="/internal", dependencies=[Depends(require_user)])` so auth always runs, keep `CurrentUser` for routes that need the id, and add a test that enumerates `app.routes` and asserts every path under `/internal` returns 401 without a token.
**Resolution:** The `/internal` router now requires `require_user` itself. Tests: every internal path in the OpenAPI schema answers 401 without a token, and a route added to the router later is protected.

Closed 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests). Re-examined: `APIRouter(prefix="/internal", dependencies=[Depends(require_user)])` is enforced under the installed FastAPI (0.162.2); the probe-route test fails if the router dependency is removed. Live against the container: unknown `/internal/*` paths are 404 and wrong methods 405 before auth (no data exposed), every matched route is 401 without the token.

### 30/F-53 [P3] closed - Request id sanitiser accepts a trailing newline

**File:** engine/src/engine/jsonlog.py:14, engine/src/engine/jsonlog.py:20
**Found:** 2026-11-07 by /audit independent (scope: current; lens: security, tests)
**Why it matters:** `_SAFE_ID.match` with a `$` anchor accepts `"abc\n"` (verified: `accept_request_id("abc\n")` returns it with the newline). HTTP parsers reject a raw newline in a header, so it is not reachable through uvicorn today, but the function exists to keep client-supplied text out of log lines and response headers, and the existing hostile-id test uses a space and a tab only.
**Suggested fix:** Use `re.fullmatch` (or `\Z`) and add `"abc\n"` and a 65-character id to the hostile cases in `test_request_id_is_echoed_or_generated`.
**Resolution:** `accept_request_id` uses a full match; a test covers a trailing newline, CRLF, overlong and empty ids.

Closed 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests). `engine/src/engine/jsonlog.py:20` uses `fullmatch`; `test_a_request_id_with_a_trailing_newline_is_replaced` fails on the old `match` form.

### 30/F-54 [P3] closed - Some engine tests would not fail if the behaviour broke

**File:** engine/tests/test_auth.py:80, engine/tests/test_auth.py:75, engine/tests/test_app.py:37, engine/tests/test_db.py:80
**Found:** 2026-11-07 by /audit independent (scope: current; lens: tests)
**Why it matters:** (1) `test_the_token_is_compared_in_constant_time` greps the source for the string `hmac.compare_digest`; it passes if the call is dead code or `==` is used next to it. A behavioural test (monkeypatch `hmac.compare_digest` and assert it is called with a wrong scheme too, or assert equal results for wrong-scheme and wrong-token) would catch real regressions. (2) `test_health_routes_need_no_token` only calls `/healthz`, not `/readyz`. (3) The `RequestValidationError` (422) handler, the 405 shape, `x-request-id` on 401/400 responses and the `readyz` timeout (a hanging, not refusing, database) have no test; the 422 handler is only reachable once a route takes input, so it ships unproven. (4) No test asserts that `create_app` makes no database connection on creation, which the spec requires (the conftest uses an unreachable URL, so it would only fail on a connect attempt that raised, not on a lazy slip that succeeds).
**Suggested fix:** Replace the source grep with a behavioural assertion, add the missing endpoint and handler tests (a temporary route taking a typed query param for 422), and add a readyz test that points at a non-routable address and expects 503 within the timeout.
**Resolution:** New tests: 422 and 405 shapes (with Allow), `/readyz` without a token, readiness timeout with a hanging database, no connection when the app is created, and the token comparison running on every attempt (spy on `hmac.compare_digest`).

Closed 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests). Each new test fails if its behaviour is removed: the spy counts four comparisons across missing header, wrong token, wrong scheme and valid; the hanging-database test fails (over 2 s) without the timeout; the 422 and 405 tests assert the stable body and `Allow`. Remaining weak spots are minor: `test_creating_the_app_opens_no_database_connection` checks a private attribute, and `x-request-id` on 401/400 responses is untested.

## Independent review

**Status:** passed
**Target commit:** 2c382f8c72ed892b38aecbe9c3584e0b41159380
**Base commit:** 3297f4fe4c908e25d38e1053dabba62871316b1a
**Base ref:** main
**Spec hash:** 88b518f881412079764b199e0a744d684bd8094963902c764d3253736d569f43
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-07T22:09:21Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-08T00:00:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, `git merge-base main <target>`, `shasum -a 256 blueprint/context/current-feature.md`, `git status --short`: pass (HEAD equals target, merge base equals Base commit, spec hash matches, only `blueprint/context/review.md` and `blueprint/context/findings.md` differ)
- `(cd web && npm run lint && npm run typecheck && npm run build && npm test) && (cd engine && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run --env-file ../.env pytest)`: pass (web 133 passed, 2 skipped live tests; engine ruff, format, mypy strict clean, 33 pytest passed)
- `uv lock --check` in `engine/`: pass (lockfile consistent with `pyproject.toml`)
- `deploy/deploy.sh --dry-run` with scratch env files via `ENV_FILE` (missing, empty, short, 31, 32, quoted 31, inline-comment, CRLF tokens): pass for the 32-character case, refused for missing, empty, short and 31; quoted and comment forms wrongly accepted (F-57)
- `docker compose -f deploy/docker-compose.prod.yml config` on a scratch copy with a scratch env file: pass (engine has no ports; only caddy publishes)
- `curl` against the running engine on port 8100 (health, readiness, no token, wrong method, unknown internal path, valid token, UUID forms, scheme case, double space, openapi and docs paths): pass, behaviour as recorded in the findings
- Node URL-parser probe of `callEngine` path forms and `Headers` request-id validation: pass (guard holds; test coverage gap F-52)
- Not run: `/check` (not required), live client test (`ENGINE_LIVE_TEST`, skipped by the suite)

## Evidence

- Delta reviewed: `git diff 3297f4f..2c382f8` (45 files: engine package, tests, migrations, Dockerfile and entrypoint, both compose files, `deploy.sh`, `docs/deploy.md`, `.env` examples, `web/src/server/engine/client.ts`, `web/src/server/errors.ts`, client tests, AGENTS.md and docs).
- Trust boundary: every `/internal` route is protected by the router-level `require_user` dependency; the probe-route test fails if it is removed; live container returns 401 without a token, constant-time compare runs on every attempt, 401 bodies are identical, token never in responses or logs (container logs inspected with the token redacted), uvicorn started with `--no-access-log`, docs and OpenAPI return 404.
- Container: runs as uid 10001, healthy, published only on 127.0.0.1:8100 in dev; production compose renders the engine with no ports; both compose files tolerate an unset token.
- Ledger re-examination: F-50, F-51, F-53, F-54 closed with evidence in their Resolution; F-52 and F-55 reopened (missing tests, remaining items); new F-56 to F-59.

## Findings

- F-50 closed (P2), F-51 closed (P2), F-53 closed (P3), F-54 closed (P3)
- F-52 open (P3): the claimed `%2e%2e` client tests do not exist
- F-55 open (P3): `ENVIRONMENT` still passed by both compose files; a 500 logs only the exception class (needs an explicit user decision to accept)
- F-56 open (P3): 30 s default client timeout not asserted
- F-57 open (P3): `deploy.sh` token length check reads the raw line, not the Compose value
- F-58 open (P3): first deploy of this release and rollback past it (old script, orphan engine container)
- F-59 open (P3): `X-User-Id` accepts non-canonical UUID forms; web request id forwarded unchecked
- No P0 or P1 finding is open or fixed.

## Remaining risk

- Only P3 findings remain open; none blocks `/complete`.
- Engine and web were reviewed against a single local environment; production deployment, Caddy routing and the real server were not exercised (out of scope by the spec).
- The live client test against the running engine was not run by this review (skipped without `ENGINE_LIVE_TEST=1`); the engine was exercised directly with `curl` instead.
- The `deploy.sh` rollback and real health-wait paths were reasoned about and dry-run only; no real server or `docker compose up` for the production file was run.
- Reviewer context and model are declared metadata and cannot be cryptographically proven.
