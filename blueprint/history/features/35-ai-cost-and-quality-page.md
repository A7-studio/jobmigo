# Feature: AI cost and quality page

**From build-plan:** feature 35
**Build attempt:** 1
**Status:** verified
**Branch:** feature/35-ai-cost-and-quality-page

## Goal

One read-only page, `/admin/ai`, for staff: what the AI calls cost and how well they went, over
the last 30 days. It makes the cost of every workflow visible so a model or prompt change can be
judged against it. It never shows posting text, profile text, quotes or model replies.

## Decisions made while specifying (change them if you disagree)

- Failures are recorded: `usage_event` gets `outcome` (`ok`, `rejected`, `failed`). `rejected` is a
  reply that did not pass validation; `failed` is a call that got no reply. Older rows are `ok`.
- The paid-model estimate uses a price the founder sets in `.env` as `AI_COMPARE_PRICE`
  (`inputUsdPerMillion,outputUsdPerMillion`) and an optional label `AI_COMPARE_LABEL`. When unset
  the page says so. No price is guessed.
- The golden-set match rate shows "Not run yet" until feature 8d exists. The page has the slot.
- "Cost per evaluation" is shown per workflow call (screen, evaluate: extract plus evidence),
  as an average per non-cached call, because the ledger holds no job id.
- Staff only: the permission is `overview.read`. There is no screen to grant staff; the founder
  adds their own row (documented in the page's empty state and in `docs`).

## In scope

- Migration `0013_usage_event_outcome.py`, model column, gateway records `rejected` and `failed`.
- Engine `GET /internal/admin/ai-usage?days=30` (all users, aggregates only), pure
  `engine/ai/usage_report.py`.
- Web: `GET /api/admin/ai-usage`, server handler checking `overview.read`, client function,
  `/admin/ai` page (summary tiles, per-workflow table, per-model and prompt table, failures,
  cache savings, paid-model estimate, golden-set slot), a staff-only link in Settings.
- Tests in engine and web; Verify passes.

## Out of scope

The golden set and `uv run eval` (8d), charts, per-user breakdowns, exporting, editing prices,
granting staff roles.

## Rules

- Aggregates only. No user ids, no text. Money is USD to cents with a "from the ledger" label;
  a row with no price counts as "cost unknown", never zero.
- Cache savings = cache hits x the average cost of a non-cached call of the same workflow and
  model; shown as an estimate.
- A non-staff user and a signed-out caller get the same refusal as every other staff route.

## Build steps

- [x] 1. Migration `0013`, model column, gateway outcomes, tests (`test_usage_event_table`,
  gateway tests); `tests/test_db.py` head `0013`.
- [x] 2. `usage_report.py` and the engine route with tests.
- [x] 3. Web handler, route, client, tests (permission refusal included).
- [x] 4. `/admin/ai` page and the Settings link for staff; lint, typecheck, build.
- [x] 5. Verify, independent review (migration, cross-user data), archive, merge.

## Notes for the AI

Reuse `forward()` from `web/src/server/profile/http.ts` and `assertPermission`. Follow the
existing handler and route tests for jobs. Keep the gateway change minimal and leave the
cache and retry behaviour as they are.

## Step notes

- Gateway: a call that gets no reply (`AiUnavailableError`) now writes one `failed` row with zero
  tokens, then raises as before. A reply that fails validation marks its row `rejected` after
  the fact. `test_ai_gateway.py` was changed to match (it asserted no row on a provider failure).
- The report reads only counts, tokens and money. A test checks that no user id appears in it.
- The web handler uses `assertPermission(session, 'overview.read')`; there is no screen to grant
  staff. To use the page the founder adds their own row, for example (psql, web database):
  `insert into staff_member (user_id, role_id) select u.id, r.id from "user" u, role r
  where u.email = '<your email>' and r.name = 'owner';`
- Verify: engine 724 passed, 10 skipped; ruff, format and mypy pass. Web lint, typecheck and
  build pass; web tests 228 passed, 1 skipped.
- Independent review 1 (a219cdb): changes-requested, F-171 (P2, workflow average) repaired.
- Engine tests after the repair: 725 passed, 10 skipped.
- Browser check: pending the engine restart, migration `0013` and a staff row.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":4231,"specSha256":"9fe5e25a6897ab6d90c1f3667a0dd72540861cefbd423cb5457ba05cfb59ac83","branch":"refs/heads/feature/35-ai-cost-and-quality-page","head":"0ae47cc41d0f92a77f06991c36f68b4c6841d701","baseRef":"refs/heads/main","baseCommit":"59a52d3093bf81e4b3de8aada839788a6c4fb562","sourceTree":"f94741bd97ca49ebb866028cfe8aeed962fd9af9","landing":"local-merge","absentOptional":[]} -->

## Findings

### 35/F-171 [P2] closed - The per-workflow "Per call" average is wrong when a rejected call has no price or when rejected calls cost money

**File:** engine/src/engine/ai/usage_report.py:200
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** The per-workflow average is `cost_usd / (calls - unknown - rejected - failed)`. The numerator includes the cost of rejected calls, and the denominator subtracts a rejected call that is also unpriced twice (once as unknown, once as rejected). Reproduced with four live `evaluate` rows: two ok at $0.01, one rejected at $0.01, one rejected with no price. The by-model row shows an average of $0.010000, the workflow row shows $0.030000 (cost 0.03 over a divisor of 1), three times too high. The page labels this column "average cost per call that gave a usable answer and had a price", so staff would overstate the cost of a workflow, the number a model or prompt change is judged against. Any rejected row with a price also inflates the numerator.
**Suggested fix:** Carry `known_cost` and `known_calls` from the query into the workflow roll-up (sum them per workflow) and compute the average from those, as the row average already does. Add a test with an unpriced rejected row.
**Resolution:** Repaired 2026-11-11: the workflow average is now the sum of known cost over the sum of known calls, the same figures the row average uses. Test: an unpriced rejected row and a priced rejected row give $0.01 on both the row and the workflow. An older assertion in `test_adds_up_calls_tokens_cost_and_failures_per_workflow` expected the buggy $0.02 and now expects $0.015.
Closed 2026-11-11 by independent review (fresh subagent, 0ae47cc): the workflow average equals the row average, checked with the added test and a probe of unpriced and priced rejected rows.

## Independent review

**Status:** passed
**Target commit:** 0ae47cc41d0f92a77f06991c36f68b4c6841d701
**Base commit:** 59a52d3093bf81e4b3de8aada839788a6c4fb562
**Base ref:** main
**Spec hash:** 9fe5e25a6897ab6d90c1f3667a0dd72540861cefbd423cb5457ba05cfb59ac83
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T14:14:04Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T14:30:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `uv run --env-file ../.env pytest -q tests/test_usage_report.py tests/test_ai_gateway.py tests/test_ai_tables.py tests/test_db.py` (engine): pass, 41 passed
- `npm test -- tests/admin` (web): pass, 11 passed
- Temporary probe test of totals and averages with small and all-rejected rows (removed afterwards): reproduced F-172 and F-173

## Evidence

- F-171 repair verified: the workflow average is now sum of known cost over sum of known calls, equal to the row figure; an unpriced and a priced rejected row give $0.01 on both.
- Migration 0013 adds a non-null `outcome` with default `ok` and a check constraint; downgrade drops both; model and head test agree.
- Gateway: failed rows are written only on `AiUnavailableError` and the error is re-raised; rejected rows are marked after the parse; retry, cache and cost paths are unchanged; no reply text is stored or logged.
- Report reads counts, tokens and money only; a test asserts no user id; window is clamped to 1..365 in the engine and validated as an integer 1..365 in the web handler after the staff check and before any engine call.
- Handler order: `requireUser` (staff check) runs first, then days validation, then the engine call; non-staff and signed-out get 403 and 401 without an engine call.
- Page and Settings link are gated on `overview.read`; all values render as text.
- Roll-up checks: workflow calls, rejected, failed, tokens, cost and unknown count equal the sum of their rows; total cost equals the sum of rows before rounding.

## Findings

- F-172 (P3, open)
- F-173 (P3, open)

## Remaining risk

- The page was not exercised in a browser (the spec notes the browser check is pending the engine restart, migration and a staff row).
- `_mark_rejected` and the failed-row write are separate commits: a database error there would replace the original error or skip the retry; not reproduced and judged unlikely.
- The average excludes rejected calls' spend by design (labelled), so retries are not reflected per call.
