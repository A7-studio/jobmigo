# Feature: Port the AI gateway and usage ledger to the engine

**From build-plan:** feature 31
**Build attempt:** 1
**Status:** verified
**Branch:** feature/port-the-ai-gateway-and-usage-ledger-to-the-engine

## Goal

Move the model gateway from the TypeScript web server (`web/src/server/ai/`, feature 2) into the
Python engine (`engine/`), so everything that calls a model lives with its data. The engine
gets the same behaviour: tier routing from environment variables, one OpenAI-compatible
provider adapter, prompt versions, schema-validated JSON output with one retry, a per-user
cache and a usage ledger that never holds text. The behaviour is proven by porting every case
of the existing `web/tests/ai-*.test.ts` files. Then the TypeScript gateway and its two tables
are removed.

## In scope

Engine (`engine/src/engine/ai/`, new package):
- **Config** (`config.py`): the provider table (DeepSeek, Moonshot, OpenRouter: URL, key
  variable, JSON-mode flag exactly as in `config.ts`), `read_tier(tier, env)` for
  `AI_CHEAP_MODEL` / `AI_STRONG_MODEL` (`provider/model-id`, the model id may contain
  slashes), optional `AI_CHEAP_PRICE` / `AI_STRONG_PRICE` (`"input,output"` USD per million
  tokens), the provider key read at call time, and `cost_usd` (six decimals, `None` without a
  price). Errors name the variable, never a value.
- **JSON handling** (`json.py`): extract one JSON value from a plain, fenced or lightly wrapped
  reply; validate against a Pydantic model; on failure return a short reason made only of
  schema field paths and error types. Keys the model chose (dict keys) are shown as `*`.
- **Provider** (`openai_compatible.py`, `httpx`): chat completions call, `response_format`
  only for providers that document it, a total time limit, one retry on a timeout, network
  error, 429 or 5xx, no retry on other 4xx, a billed reply with no text returns empty text
  with its tokens, missing usage counts as zero. Never logs prompts, replies, headers or keys.
- **Tasks and gateway** (`tasks.py`, `gateway.py`): `AiTask` (name, workflow, tier, prompt
  version, system and user prompt, input and output Pydantic models, `cache` flag defaulting
  to true, time limit) and `run_task(task, raw_input, *, user_id, database, env, provider)`:
  validate input before any call, read the tier, serve a valid cached result (writing a
  zero-token usage row with `cache_hit` true), otherwise call the provider, write one usage
  row for every response, validate the reply with one retry that tells the model which
  fields were wrong (never the reply itself), cache the validated output, fail visibly after
  a second invalid reply. A cached value that no longer fits the output model is a miss.
- **Errors** (`errors.py`, `ApiError` subclasses with the existing stable `{code, message}`
  shape): `ai_not_configured` 503, `ai_unavailable` 502, `ai_output_invalid` 502,
  `ai_input_invalid` 400, with the messages from `errors.ts`.
- **Tables** (Alembic migration `0002`, models in `models.py`, schema `engine`): `usage_event`
  and `ai_cache` with the same columns, constraints and index as `schema.ts` (workflow check,
  non-negative tokens, `(user_id, created_at)` index, cache primary key `(user_id,
  cache_key)`), `user_id` a plain `uuid` with no foreign key (the engine never references the
  web schema; deletion by user id arrives with the account-deletion feature).
- **Wiring**: `httpx` becomes a runtime dependency (it was dev-only); the AI variables are
  passed to the engine container in `docker-compose.yml`, `deploy/docker-compose.prod.yml`
  and documented in `deploy/.env.production.example`; `AGENTS.md` and
  `docs/technical-design.md`, `docs/database-design.md` describe the new home; a live test
  (`AI_LIVE_TEST=1`) makes one real call and checks the ledger.

Web (removal, last step): delete `web/src/server/ai/`, `web/tests/ai-*.test.ts`, the
`usage_event` and `ai_cache` tables and `AI_WORKFLOWS` from `web/src/server/db/schema.ts`, the
four `Ai*Error` classes from `web/src/server/errors.ts`, the two cases in
`web/tests/schema.test.ts`, and add the Drizzle migration that drops the two tables.

## Out of scope

- Any HTTP route or web caller for the gateway (the first task, CV parsing in 3b, adds them).
- Real prompts or tasks (3b), provider or model choices (the user picks the tier ids before
  3b), bring-your-own-key, streaming, tool calls, embeddings.
- Copying existing rows: the two tables hold only local test data and nothing is deployed;
  they are dropped, not migrated.
- Account deletion by user id, usage reporting screens, credit metering (feature 16).
- Changes to the web engine client, auth between the services or the CV features.

## Build loop

`workflow.stepReview: feature`; `workflow.checkpointCommits: disabled`. Run the narrow check
per step; run the full Verify once at the end. Use the TypeScript cases as the test list: each
Python test names the TypeScript case it ports. The removal in step 7 happens only after the
Python suite is green. Independent review follows `qualityGates.regular` (this touches a
model-provider boundary and secrets, so it is likely selected; `/complete` decides).

## Build steps

- [x] 1. **Config and errors.** Add `engine/src/engine/ai/{__init__,errors,config}.py`, move
  `httpx` to runtime dependencies (`pyproject.toml`, `uv.lock`), and port `ai-config.test.ts`
  (9 cases) to `engine/tests/test_ai_config.py`. Done when: ruff, format, mypy and the new
  tests pass; no error message or log contains a configured value.
- [x] 2. **JSON extraction and output parsing.** Add `json.py` and port `ai-json.test.ts`
  (10 cases) to `engine/tests/test_ai_json.py`, including the field-path privacy cases
  (dict keys become `*`, names survive lists and optional fields). Done when: checks pass.
- [x] 3. **Provider adapter.** Add `openai_compatible.py` and port `ai-provider.test.ts` (11
  cases) to `engine/tests/test_ai_provider.py` using `httpx.MockTransport` (no network).
  Done when: checks pass, including the total time limit, the single retry rule and the
  never-logs case.
- [x] 4. **Tables.** Add `UsageEvent` and `AiCache` to `models.py` and Alembic `0002`; port
  the two `schema.test.ts` ledger cases to `engine/tests/test_ai_tables.py`. Done when: from
  an empty `jobmigo_engine_test` database `alembic upgrade head` creates both tables in
  schema `engine` with the constraints and index, a bad workflow and negative tokens are
  rejected, a duplicate cache key for one user is rejected, `downgrade` removes them, and the
  checks pass.
- [x] 5. **Tasks and gateway.** Add `tasks.py` and `gateway.py` and port `ai-gateway.test.ts`
  (16 cases) to `engine/tests/test_ai_gateway.py` with a fake provider and the test
  database. Done when: checks pass, including per-user cache isolation, prompt-version and
  model misses, the one retry that records both calls, no usage row when the provider fails,
  a null cost without a price, the opt-out from caching, and a log capture proving prompts,
  inputs and outputs are never logged.
- [x] 6. **Wiring, docs and live test.** Pass the AI variables to the engine in both compose
  files and `.env.production.example`; update `AGENTS.md`, `docs/technical-design.md` and
  `docs/database-design.md`; add `engine/tests/test_ai_live.py` (skipped unless
  `AI_LIVE_TEST=1`). Done when: `docker compose config` shows the variables on the engine
  service and no secret value is printed by any script; the live test is collected and
  skipped; ruff, format, mypy and pytest pass.
- [x] 7. **Remove the TypeScript gateway.** Delete the web files listed above, run
  `npm run db:generate` for the migration that drops `usage_event` and `ai_cache`, and update
  `schema.test.ts`. Done when: `npm run lint`, `typecheck`, `build` and `test` pass; a fresh
  database migrates with `npm run db:migrate`; `usage_event` and `ai_cache` no longer exist in
  `public`; and `rg "server/ai"` finds nothing in `web/src`.

## Files / areas

- `engine/src/engine/ai/*` (new), `engine/src/engine/models.py`,
  `engine/migrations/versions/0002_*.py`, `engine/pyproject.toml`, `engine/uv.lock`,
  `engine/tests/test_ai_*.py`.
- `docker-compose.yml`, `deploy/docker-compose.prod.yml`, `deploy/.env.production.example`,
  `.env.example`, `AGENTS.md`, `docs/technical-design.md`, `docs/database-design.md`.
- `web/src/server/ai/` (deleted), `web/src/server/db/schema.ts`, `web/src/server/errors.ts`,
  `web/tests/` (ai tests deleted, `schema.test.ts`), `web/drizzle/0003_*.sql` and meta.

## Data / contracts

- **Ledger row** (`engine.usage_event`): `id uuid` (generated), `user_id uuid not null`,
  `workflow text` in (`parse`, `screen`, `evaluate`, `tailor`, `reach_check`, `outreach`),
  `provider`, `model`, `prompt_version` text, `tokens_in`, `tokens_out` integer `>= 0`,
  `cost_usd numeric(12,6)` nullable (null when no price is configured), `cache_hit boolean`,
  `created_at timestamptz` default now. One row per model response, plus one per cache hit.
  It never holds prompts, inputs or outputs.
- **Cache row** (`engine.ai_cache`): primary key `(user_id, cache_key)`; `cache_key` is the
  SHA-256 hex of the canonical JSON (sorted keys, no spaces) of `{task, prompt_version,
  model: "provider/model", input}`; `task`, `prompt_version`, `output jsonb`, `created_at`.
  Per user, so results are never shared between users.
- **Errors**: stable codes above; messages never echo a configuration value, a reply or a key.
- **Environment**: `AI_CHEAP_MODEL`, `AI_STRONG_MODEL`, `AI_CHEAP_PRICE`, `AI_STRONG_PRICE`,
  `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`, `OPENROUTER_API_KEY`, read at call time; missing
  or malformed settings fail the call with `ai_not_configured`, not at startup.
- **Trust boundary**: `user_id` comes from the already-verified internal request (a later
  route passes the `X-User-Id` value); the gateway scopes every cache read and write by it.

## Testing

- Every case of the four non-live `ai-*.test.ts` files is ported (46) plus the two schema
  cases; each Python test names its TypeScript source case. Provider tests use
  `httpx.MockTransport`; gateway and table tests use the `jobmigo_engine_test` database; the
  live test is skipped by default and is the only one that needs a provider key.
- Not claimed: real provider behaviour (the live test is not run without a key and chosen
  model), account deletion, multi-process concurrency beyond the upsert on the cache key.
- Baseline observed while specifying: web lint, typecheck and build clean, 133 passed and 2
  skipped; engine ruff, format and mypy clean, 33 tests passed.

## Notes for the AI

- Port behaviour, not syntax: Zod issue codes become Pydantic error types in the reason
  text; the rule (field names and types only, dict keys as `*`) is the contract.
- Python 3.13, strict mypy, async SQLAlchemy and asyncpg as in feature 30; no new package
  other than moving `httpx` to runtime. Use `Decimal` for cost to avoid float drift.
- The httpx timeout is per phase, so enforce the total limit with `asyncio.timeout`.
- Keep the old TypeScript files until step 7 so each ported case can be compared.
- Added while building (mechanical, same boundary): the port does not carry forward four known
  open findings from the TypeScript gateway. A failed cache write is best effort and logs only a
  code (F-47); a 200 reply with an error body is `ai_unavailable` and array content parts are
  joined (F-48); NaN or infinity in an input is rejected instead of hashing to a shared key
  (F-42); stored output is the validated model dumped to JSON (F-46). Each has a test.
- The overview (`blueprint/context/project-overview.md`) still says feature 2 is TypeScript
  and "moves to the engine in 31"; after completion it needs a `/overview` run to drop that,
  trimming wording to stay under its 20,000-byte limit (it is at 19,995 bytes).

## Open questions

- Non-blocking, decided here: the existing rows in `public.usage_event` and `public.ai_cache`
  are discarded (local test data only, nothing deployed). Say so before building if you want
  them kept.
- Non-blocking: the user still has to choose the cheap and strong provider/model ids and
  confirm the privacy notice names the provider, both before CV parsing (3b), not here.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":12264,"specSha256":"190e19fba54d3a2a8cce12a89ee0ca389efb50a9e8ecdafc5e10b33043c2f097","branch":"refs/heads/feature/port-the-ai-gateway-and-usage-ledger-to-the-engine","head":"246165ce4d4026a8bcaa6cfadae2ddcb1bdc8db9","baseRef":"refs/heads/main","baseCommit":"bca1f6cd42249d8b72a5bf7dc8907e952c1e418f","sourceTree":"f0ece9b5c1b2095201ef4e91fed8f7ff2a7de6e7","landing":"local-merge","absentOptional":[]} -->


## Independent review

**Status:** passed
**Target commit:** 246165ce4d4026a8bcaa6cfadae2ddcb1bdc8db9
**Base commit:** bca1f6cd42249d8b72a5bf7dc8907e952c1e418f
**Base ref:** refs/heads/main
**Spec hash:** 190e19fba54d3a2a8cce12a89ee0ca389efb50a9e8ecdafc5e10b33043c2f097
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-08T00:31:00Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-opus-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-08T00:36:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

### Handoff

Review the active spec and the complete `<base>..<target>` delta in a fresh
session or isolated subagent without the builder conversation. Run all Audit lenses from scratch.
Run Check when required above. Do not edit product code, accept findings, or
reuse the existing findings as the review scope.

### Commands

- `git rev-parse HEAD`, `git merge-base refs/heads/main HEAD`, `shasum -a 256 blueprint/context/current-feature.md`, `git status --porcelain --untracked-files=all`: pass (HEAD, merge base and spec hash match the request; only `blueprint/context/review.md` differed)
- `git diff bca1f6c..246165c` (all 45 files): reviewed
- `cd engine && uv run ruff check . && uv run ruff format --check . && uv run mypy`: pass
- `cd engine && uv run --env-file ../.env pytest -q`: pass (96 passed, 1 skipped: the live test)
- `cd web && npm run lint && npm run typecheck`: pass
- `rg "server/ai|usageEvent|aiCache|AiUnavailable|AI_WORKFLOWS" web/src web/tests`: no matches
- Pydantic probes (`uv run python -c ...`): NaN and infinity inputs are refused by `canonical_json`; an aliased output model does not revalidate from its own `model_dump(mode="json")`

### Evidence

- Cache isolation: the read (`gateway.py:190-194`) filters on `user_id` and `cache_key`; the upsert (`gateway.py:126-139`) writes `user_id` and conflicts on the `(user_id, cache_key)` primary key; `test_never_serves_one_user_the_cache_of_another` passes.
- No text in logs, errors or ledger: provider logs only provider, status, attempt and duration; the gateway logs task, provider, model and the field-path reason; `UsageEvent` has no text columns; errors carry fixed messages and name variables, never values. The engine logger is the only configured handler; httpx logs are not emitted. A failed cache write logs only `ai_cache_write_failed` (F-47 repaired in the port).
- Retry and timeout: `asyncio.timeout` bounds each provider attempt including the body read; one retry on network, timeout, 429 and 5xx, none on other 4xx, non-JSON or a 200 error body; redirects are not followed (httpx default). Gateway retries once on invalid output, records every billed response, writes no row when the provider fails. Behaviour matches the deleted TypeScript adapter and gateway.
- Migrations: Alembic `0002` matches `models.py` and the old Drizzle columns, checks and index; downgrade is tested. Drizzle `0003` drops `public.ai_cache` and `public.usage_event` with no `IF EXISTS`; the spec explicitly discards that local test data.
- Compose: the engine service receives the seven AI variables in both compose files with empty defaults; the local web service does not; the production web service still does via `env_file` (F-62).
- Tests: all 46 TypeScript cases plus the two schema cases have named Python ports (the `defineTask` case lives in the gateway file; the timeout-retry part of the network case is covered by the time-limit test), plus new tests for F-42, F-47 and F-48.

### Findings

- F-60 [P3] open: aliased output models never hit the cache
- F-61 [P3] open: gateway test gaps carried over from F-49
- F-62 [P3] open: production web container still receives provider keys
- F-63 [P3] unverified: per-attempt HTTP client and long worst-case duration
- No P0 or P1 finding

### Remaining risk

- Web `npm run build` and `npm test` were not run by this reviewer; `npm run db:migrate` on a fresh database and `docker compose config` were not re-run.
- The live provider test (`AI_LIVE_TEST=1`) was not run: no real provider call was made.
- The engine tables have no foreign key, so the cascade delete the old web tables had is gone; `engine.ai_cache` holds CV-derived output and must be deleted by user id when account deletion lands (accepted in the spec as out of scope; no deletion path exists today).
- `engine.ai_cache` has no expiry (the lead in F-45 still applies to the port).


## Try it now

These are instructions for you to follow; they were not performed by you. In the repository root:

1. Start the database (`docker compose up -d db`), then in `engine/` run `uv run --env-file ../.env pytest tests/test_ai_config.py tests/test_ai_json.py tests/test_ai_provider.py tests/test_ai_tables.py tests/test_ai_gateway.py`. All pass without a network or a provider key; the live test is reported as skipped.
2. Apply the migration to your dev database with `cd web && npm run db:migrate` (it drops the two old tables in `public`, which held only local test data), then check in `psql` that `engine.usage_event` and `engine.ai_cache` exist after the engine has started (the engine container runs its Alembic migrations on start: `docker compose up -d --build engine`).
3. When you have chosen a provider and model, put `AI_CHEAP_MODEL=<provider>/<model-id>` and its API key in `.env`, then run `AI_LIVE_TEST=1 uv run --env-file ../.env pytest tests/test_ai_live.py` in `engine/`. It makes one real call, caches the answer, makes the same call again from the cache, and checks two ledger rows.
