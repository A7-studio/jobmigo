# Feature: AI gateway and usage ledger

**From build-plan:** feature 2
**Build attempt:** 1
**Branch:** feature/ai-gateway-and-usage-ledger
**Status:** verified

## Goal

Every later AI feature (CV parsing, evaluation, tailoring) calls one server-side
gateway instead of a model provider. The gateway picks the model from the task,
sends a versioned prompt, validates the answer against a schema, reuses cached
results, and writes a usage-ledger row for every call so cost per user and per
workflow is always known. It works with free or cheap OpenAI-compatible
providers (DeepSeek, Kimi, OpenRouter) through plain configuration, so the
founder can test it locally with their own keys. No user-facing screen changes
and no model-backed feature ships here.

## In scope

- **Provider interface** (`AiProvider`) with one adapter for the OpenAI-compatible
  chat-completions API, using plain `fetch` (no SDK, like the Resend adapter).
  A small code registry maps provider names to base URLs and the environment
  variable holding each key: `deepseek` (`DEEPSEEK_API_KEY`), `moonshot`
  (`MOONSHOT_API_KEY`), `openrouter` (`OPENROUTER_API_KEY`). Exact base URLs are
  confirmed against each provider's public docs while building step 2.
- **Routing config, not call sites:** two tiers, `cheap` and `strong`, each set by
  an environment variable `AI_CHEAP_MODEL` / `AI_STRONG_MODEL` in the form
  `provider/model` (for example `deepseek/<model-id>`). Optional
  `AI_CHEAP_PRICE` / `AI_STRONG_PRICE` as `inputUsdPerMillion,outputUsdPerMillion`.
  No default model ids are shipped (they would be unverified guesses); an unset
  tier fails visibly with an `ai_not_configured` error naming the variable.
- **Task registry:** a task is a typed definition: `name`, `workflow`
  (parse | screen | evaluate | tailor | reach_check | outreach), `tier`, a versioned
  prompt (`version`, `system`, a function building the user message from the
  input), an input and output zod schema, and a `cache` flag (default on).
  Real tasks arrive with the features that need them, as files under
  `web/src/server/ai/prompts/`; this feature ships the registry type and
  test-only tasks.
- **Gateway** `runTask(task, input, { userId })` in `web/src/server/ai/gateway.ts`:
  1. validate the input; 2. cache lookup; 3. on a miss, call the provider
  (timeout, one retry on 429, 5xx or timeout); 4. extract JSON from the reply
  (accepting a fenced block), validate against the output schema; on failure
  retry the model once with the validation error, then throw
  `ai_output_invalid`; 5. write a usage event for every provider response
  received (including the retried one); 6. store the validated output in the
  cache; 7. return `{ output, cacheHit, promptVersion, usageEventId }`.
- **Cache:** keyed by SHA-256 of canonical JSON of task name, prompt version,
  model id and input, and **scoped per user** so one user's result is never
  served to another. A hit writes a usage event with `cache_hit = true`, zero
  tokens and zero cost, and is revalidated against the current output schema
  (a stale shape is treated as a miss).
- **Usage ledger table** `usage_event` (design in `docs/database-design.md`) and
  cache table `ai_cache`, as one drizzle-kit migration.
- **Errors** as `DomainError` subclasses with stable codes: `ai_not_configured`
  (503), `ai_unavailable` (502, provider failed after retry),
  `ai_output_invalid` (502, still invalid after retry), and `ai_input_invalid`
  (400) for inputs that fail the task's schema.
- **Privacy:** prompts, inputs, outputs, keys and CV text are never logged. Log
  lines carry task name, provider, model, status and duration only. Provider
  error bodies are not logged.
- **Local testing path:** a Vitest smoke test against the real provider that is
  skipped unless `AI_LIVE_TEST=1`, so the founder can check their own keys
  without a UI. Docs and `.env.example` updated.

## Out of scope

- Any real prompt or user-facing AI feature (CV parse is feature 3, evaluation 8,
  kit 11).
- Credits, plan quotas, entitlement checks and per-user spend caps (feature 16);
  admin cost views and kill switches (feature 23). The ledger rows these will read
  are written here.
- Bring-your-own-key (the interface leaves room, nothing is built).
- Streaming responses, tool calling, embeddings, and multiple fallback providers
  per tier.
- Background queue execution (the gateway is a plain async function; the worker
  and queue arrive with the first long-running AI feature).
- HTTP routes or server functions exposing the gateway to the browser. Callers
  are server code that already took the user id from the session.

## Build loop

Per `blueprint/config.json`: `workflow.stepReview: feature` (one review packet at
the end) and `workflow.checkpointCommits: disabled`. Build the steps in order on
the branch above, run the narrowest check while iterating, run Verify once after
the last step, then a fresh independent review (this work handles personal data
paths and an external service, so `when-sensitive` selects it).

## Build steps

- [x] 1. **Schema and migration.** Add `usage_event` and `ai_cache` to
  `web/src/server/db/schema.ts`; generate and review the drizzle migration;
  extend `tests/helpers.ts` `resetData` and `tests/schema.test.ts` for the new
  tables. Done when `npm run db:migrate` applies cleanly to a fresh database, the
  check constraints reject an unknown `workflow` and negative tokens, deleting a
  user cascades their rows, and `npm test` passes.
- [x] 2. **Provider layer and configuration.** `web/src/server/ai/provider.ts`
  (interface and types), `openai-compatible.ts` (adapter with injected `fetch`,
  timeout, one retry on 429, 5xx or timeout, token counts from the response),
  `config.ts` (provider registry, tier parsing from `AI_*` variables, price
  parsing, `ai_not_configured` errors), and the error classes in
  `web/src/server/errors.ts`. Done when unit tests with a fake `fetch` cover: a
  good response, a 429 then success, a persistent 500, a timeout, a missing key,
  an unset tier, a malformed `AI_CHEAP_MODEL`, and price parsing (including cost
  from tokens); and no test asserts on logged text containing a prompt.
- [x] 3. **Task registry and validated output.** `tasks.ts` (task definition type)
  and `json.ts` (extract JSON from plain or fenced replies). Done when tests cover:
  fenced and bare JSON, trailing prose, invalid JSON, and schema mismatch
  reporting a short error string with no model text echoed into logs.
- [x] 4. **Gateway with cache and ledger.** `web/src/server/ai/gateway.ts`
  implementing the flow in scope. Done when database-backed tests with a fake
  provider prove: a miss writes one usage event with provider, model, prompt
  version, tokens and computed cost, then caches; the same input again is a hit
  with `cache_hit = true`, zero tokens and no provider call; a different user with
  the same input does not hit the first user's cache; a changed prompt version or
  model misses; invalid output retries once and records both calls; a second
  invalid output throws `ai_output_invalid` and caches nothing; a provider failure
  throws `ai_unavailable` and writes no usage row; an invalid input throws
  `ai_input_invalid` before any provider call; a tier with no configured model
  fails before any call; a stale cached shape is treated as a miss.
- [x] 5. **Docs, env and live smoke test.** Update `.env.example` (replace the
  `AI_PROVIDER_KEYS` placeholder with the variables above and a worked example),
  `docs/technical-design.md` (section 11 and the config-names line),
  `docs/ai-workflows.md` pointer to the code location, and the Commands section
  of `AGENTS.md` with how to run the live smoke test. Add
  `tests/ai-live.test.ts`, skipped unless `AI_LIVE_TEST=1`. Done when
  `npm run lint && npm run typecheck && npm run build && npm test` passes with the
  live test reported as skipped, and the docs name every new environment variable.
- [x] 6. **Repair review findings.** F-40 (a billed reply with no content now
  records its usage and retries), F-41 (empty parts in `AI_*_PRICE` rejected),
  F-43 (validation reasons show only schema field names, never model-chosen
  keys), F-44 (optional per-task `timeoutMs` passed to the provider, abort
  covered by a test). Done when the new tests for each pass and
  `npm run lint && npm run typecheck && npm run build && npm test` passes.

## Files / areas

- New: `web/src/server/ai/{provider,openai-compatible,config,tasks,json,gateway}.ts`,
  one drizzle migration under `web/drizzle/`,
  `web/tests/{ai-config,ai-provider,ai-json,ai-gateway,ai-live}.test.ts`
- Changed: `web/src/server/db/schema.ts`, `web/src/server/errors.ts`,
  `web/tests/helpers.ts`, `web/tests/schema.test.ts`, `.env.example`,
  `docs/technical-design.md`, `docs/ai-workflows.md`, `AGENTS.md`
- Untouched: routes, components, deployment files (production env vars are added
  when the first AI feature ships to users)

## Data / contracts

- `usage_event`: `id` uuid pk (random), `user_id` uuid not null references `user`
  on delete cascade, `workflow` text with check in (parse, screen, evaluate,
  tailor, reach_check, outreach), `provider` text, `model` text,
  `prompt_version` text, `tokens_in` integer >= 0, `tokens_out` integer >= 0,
  `cost_usd` numeric(12,6) nullable (null when the tier has no price configured),
  `cache_hit` boolean not null, `created_at` timestamptz default now. Index on
  `(user_id, created_at)`. Holds no prompt or output text.
- `ai_cache`: primary key `(user_id, cache_key)`; `user_id` references `user` on
  delete cascade; `cache_key` text (SHA-256 hex); `task` text; `prompt_version`
  text; `output` jsonb; `created_at` timestamptz default now. Rows are the
  user's own derived data and are removed with the user.
- Provider contract: `complete({ model, system, user, timeoutMs })` returns
  `{ text, tokensIn, tokensOut }`. The adapter sends
  `POST {baseUrl}/chat/completions` with a bearer key, and adds
  `response_format: { type: "json_object" }` only when the registry marks the
  provider as supporting it.
- Gateway result: `{ output, cacheHit, promptVersion, usageEventId }`; errors are
  `DomainError` subclasses (`{ code, message }`), never raw provider messages.
- Cache key: `sha256(canonicalJson({ task, promptVersion, model, input }))` with
  object keys sorted, plus the `user_id` column.
- Cost: `tokens_in / 1e6 * inputPrice + tokens_out / 1e6 * outputPrice`, rounded to
  6 decimals.

## Testing

Vitest with the real `jobmigo_test` database for gateway and schema tests, and a
fake `fetch` for the provider adapter (no network in tests). Tests cover the
done-when lists above. The live smoke test calls the real provider once with a
tiny task and checks that the reply validates and a usage row exists; it runs
only with `AI_LIVE_TEST=1` and real keys, and is not part of Verify. No browser
tests (no UI).

## Notes for the AI

- Follow the existing patterns: injected `fetch` like `ResendProvider` in
  `web/src/server/mail.ts`, `DomainError` for stable codes, the JSON logger, and
  tests that use `resetData`.
- Never log prompts, inputs, outputs, headers or keys. Treat the provider response
  body as sensitive; on a non-2xx status log only the status code.
- Read keys from `process.env` at call time (not import time) so tests and local
  edits take effect; never copy a key into an error message.
- Do not add an SDK, a queue, or a fallback chain. The interface is the seam for
  those later.
- Confirm provider base URLs and `response_format` support from each provider's
  public documentation during step 2 and record what was confirmed; where it
  cannot be confirmed, leave the provider out of the registry rather than guess.
- Task input and output types come from the task's zod schemas so later features
  get typed results.
- Prompt `version` strings are what the ledger and cache key record, so a prompt
  edit must bump its version (feature 8's golden set depends on this).

## Open questions

None that block the build. Worth deciding before feature 3: which provider and
model ids you will use for the cheap and strong tiers (the spec leaves them to
environment variables). Free-tier providers may log or train on prompts; that
matters for CV text and belongs in the privacy notice before real users send CVs
through them.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":12363,"specSha256":"fb6ba87f353121d1451c10a7cca58ddb99da14aee77321273b12747cb5ad0033","branch":"refs/heads/feature/ai-gateway-and-usage-ledger","head":"6eb98e484ad7052b977612cf73474f7cc7eacb20","baseRef":"refs/heads/main","baseCommit":"5653741ebd162b20f52090fb807c1eb9b6e7fa29","sourceTree":"8514d1c2b40fc0208480cb6523aae773d0312007","landing":"local-merge","absentOptional":[]} -->

## Findings

### 2/F-40 [P2] closed - A 200 reply with no usable content is billed by the provider but writes no usage row

**File:** web/src/server/ai/openai-compatible.ts:104
**Found:** 2026-11-07 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** The spec says a usage event is written "for every provider response received". When the provider answers 200 but `choices` is empty, `message.content` is null (a refusal, a reasoning-only reply, a length cutoff) or the body is not JSON, `attempt()` returns a non-transient failure and the gateway throws `ai_unavailable` before `record()` runs, even though the body usually carries `usage` and the provider has charged for the tokens. Spend then goes missing from the ledger that later credits and cost views read, and a transient odd shape is never retried. `tests/ai-provider.test.ts:105` asserts this behaviour (single fetch, `AiUnavailableError`) and `tests/ai-gateway.test.ts:252` only covers a provider that throws, so nothing would catch a fix or a regression either way. A blank-string reply is handled correctly (it reaches the schema check and the retry).
**Suggested fix:** When the body parses as JSON, return `text: ''` (or `null`) together with the counted tokens for a missing or null `content`, so the gateway records the usage, rejects the reply as invalid and retries once under the normal rule. Reserve `ai_unavailable` for a non-2xx status or an unparseable body, and add a gateway test that a 200 with null content and a `usage` block writes a usage row.
**Resolution:** Feature 2 repair step 6: a 200 reply with no content now returns empty text with the counted tokens, so the gateway records a usage row, rejects the reply as invalid and retries once. Only a non-2xx status or an unparseable body is `ai_unavailable`. Tests: provider returns empty text with tokens for empty `choices` and null content; the gateway records both calls of a billed empty reply. Pending re-review.
Closed 2026-11-07 by independent review (fresh subagent): adapter returns empty text with counted tokens for empty `choices` or null `content` (openai-compatible.ts:101-113); gateway records a usage row before parsing (gateway.ts:139-146) and retries once; provider and gateway tests for both shapes pass and would fail if the record call moved after the parse. A 200 with an `error` body is a separate lead, see F-48.

### 2/F-41 [P3] closed - A trailing comma in `AI_*_PRICE` silently sets the output price to zero

**File:** web/src/server/ai/config.ts:60
**Found:** 2026-11-07 by /audit independent (scope: current; lens: quality)
**Why it matters:** `Number('')` is 0, so `AI_CHEAP_PRICE="5,"` or `","` passes validation (verified: `"5,"` parses to input 5, output 0). A typo makes every call record an under-stated cost with no error, which is the opposite of the "fail visibly" intent for configuration. The test list (`1`, `a,b`, `-1,2`, `1,2,3`) does not include an empty part.
**Suggested fix:** Reject an empty part before converting (`part.trim() === ''`) and add `'5,'`, `',5'` and `','` to the malformed-price test.
**Resolution:** Empty parts in `AI_*_PRICE` are rejected; the malformed-price test now includes `5,`, `,5` and `,`. Pending re-review.
Closed 2026-11-07 by independent review: config.ts:56-70 maps empty parts to NaN and throws; test covers `5,`, `,5`, `,`.

### 2/F-43 [P3] closed - Validation failure reason can echo model-generated object keys into logs and the retry prompt

**File:** web/src/server/ai/json.ts:48
**Found:** 2026-11-07 by /audit independent (scope: current; lens: security)
**Why it matters:** The reason is built from `issue.path`, which contains the model's own keys when an output schema uses `z.record` or a catchall (verified: a reply key `"cv secret name"` appears verbatim in the reason). That string is logged by `ai output rejected` (gateway.ts:185) and sent back to the provider, so CV-derived text the model chose as a key can reach logs, contrary to "prompts, inputs, outputs ... never logged". The existing test only covers a fixed-shape object, so the "no model text echoed" guarantee holds only for such schemas.
**Suggested fix:** Report only numeric indexes and the depth or the issue code for path segments that are not statically known (for example drop string segments after the first or replace them with `*`), and add a `z.record` test asserting the key is absent.
**Resolution:** Validation reasons are built from names found in the schema itself; model-chosen keys show as `*`. Tests: a `z.record` key is absent from the reason, and known names survive through arrays and optional objects. Pending re-review.
Closed 2026-11-07 by independent review: json.ts reason uses only `issue.code` and schema-declared names (record keys and unknown paths become `*`); tests cover record keys and nested optional paths. No model text reaches the log or the retry prompt.

### 2/F-44 [P3] closed - No overall deadline on a task, and the timeout path is not tested

**File:** web/src/server/ai/openai-compatible.ts:91, web/src/server/ai/gateway.ts:138
**Found:** 2026-11-07 by /audit independent (scope: current; lens: performance, tests)
**Why it matters:** The gateway never passes `timeoutMs`, so each fetch uses a fixed 60 s. A provider that hangs costs up to 2 x 60 s inside the adapter and the gateway may then call again after an invalid reply, so one request can hold a server worker for about four minutes plus back-off. A task cannot choose a shorter limit and callers (future server functions) have no deadline to rely on. `tests/ai-provider.test.ts:89` simulates the timeout by rejecting with a plain Error; nothing proves `AbortSignal.timeout` is wired to `timeoutMs` or that a hung body read aborts, so removing the signal would still pass.
**Suggested fix:** Add an optional `timeoutMs` to the task definition passed through to the provider, and consider a total budget across both gateway attempts. Add a test with a fake fetch that honours `init.signal` and a tiny `timeoutMs`.
**Resolution:** Tasks take an optional `timeoutMs`, passed to the provider on every call; a test with a fake fetch that honours the abort signal proves the timeout fires and the call is retried once. A total budget across both gateway attempts was not added. Pending re-review.
Closed 2026-11-07 by independent review: `timeoutMs` flows task -> gateway -> `AbortSignal.timeout` on the fetch (covers the body read) and an abort-honouring test proves two attempts then `ai_unavailable`. The absent total budget across both gateway attempts is a design choice outside the spec's contract; noted under remaining risk.

## Independent review

**Status:** passed
**Target commit:** 6eb98e484ad7052b977612cf73474f7cc7eacb20
**Base commit:** 5653741ebd162b20f52090fb807c1eb9b6e7fa29
**Base ref:** main
**Spec hash:** fb6ba87f353121d1451c10a7cca58ddb99da14aee77321273b12747cb5ad0033
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-07T20:12:31Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-07T20:30:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `shasum -a 256 blueprint/context/current-feature.md`, `git status --short`: pass (HEAD equals target, merge base equals base, spec hash matches, only review.md differs)
- `npm run lint && npm run typecheck && npm run build && npm test` (in web/): pass (11 files passed, 1 skipped; 123 tests passed, 1 skipped live test)

## Evidence

- Reviewed `git diff 5653741..6eb98e4` for the AI gateway, provider adapter, config, JSON extraction, schema, migration 0002, errors, tests, docs and env example.
- Closed F-40, F-41, F-43, F-44 after re-reading the repaired code and tests; added F-47 (P2), F-48 and F-49 (P3); F-42, F-45, F-46 remain open or unverified (P3).
- No prompt, input, output, header or key reaches a log line or domain error message in the reviewed paths; the only leak vector found is a raw Drizzle error on a failed cache write (F-47).

## Findings

- F-47 (P2, open), F-48 (P3, open), F-49 (P3, open); carried: F-42 (P3, open), F-45 (P3, unverified), F-46 (P3, unverified). Closed: F-40, F-41, F-43, F-44. No P0 or P1 is open or fixed.

## Remaining risk

- A failed `ai_cache` write fails a paid call and can surface model output in a Drizzle error message (F-47); fix before a caller logs error messages.
- No total deadline across the gateway's two attempts (up to about four minutes per task at default timeouts).
- Concurrent identical calls for one user both reach the provider (no in-flight dedupe); acceptable at current scale.
- The live provider smoke test and real provider base URLs and `response_format` support were not exercised (no network calls made).
