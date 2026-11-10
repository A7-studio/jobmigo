# Feature: Job table and paste (engine)

**From build-plan:** feature 29a
**Build attempt:** 1
**Branch:** feature/job-table-and-paste
**Status:** verified

## Goal

A signed-in user can paste a job posting (text, or saved page HTML) with its company and title, and
Jobmigo stores a cleaned copy, flags anything suspicious, refuses duplicates, and lets the user save
or dismiss the job. No fetching of links (29b), no screens (29c), no scoring (feature 8).

## Design reference

None: engine and proxy routes only. The Jobs and Job boards are built in 29c.

## In scope

- `engine/src/engine/jobs/posting_guard.py`: the posting cleaner, ported from ai-job-search
  (MIT, Copyright (c) 2026 Mads Lorentzen) with the notice in `THIRD_PARTY_NOTICES.md`, adapted to a
  library (no command line, no file or stdin handling), the instruction patterns reworded for this
  product, and results kept as counts (never excerpts).
- Migration 0008 and models for `job`; engine routes under `/internal/jobs`; web proxy routes
  `/api/jobs/**` and a typed client.
- Deduplication, the light legitimacy flag, the saved and dismissed state, a per-user cap.

## Out of scope

Fetching a link or reading robots.txt (29b); the screens (29c); extracting company and title from
the text (the user supplies them for now); scoring, evaluation, discovery; `job_key.py` from the
source repo (a short slug is enough here).

## Build steps

- [x] 1. **The cleaner.** `posting_guard.py` (`guard(raw, mode) -> (text, Findings)`), the notice
  file, and `engine/tests/test_posting_guard.py`. Done when tests cover hidden HTML, invisible and tag
  characters, instruction-shaped lines (and everyday prose that must not match), mixed-script words,
  that findings hold counts only, and the full engine Verify passes.
- [x] 2. **Table, service and routes.** Migration 0008, `Job` model, `engine/src/engine/jobs/*`,
  mounted at `/internal/jobs`. Done when tests cover create, duplicates, list filters, get, status
  change, delete, ownership, validation bounds, the body cap, the per-user cap, the flag and that
  stored text is the cleaned text; full engine Verify passes.
- [x] 3. **Web proxy and client.** `web/src/server/jobs/http.ts`, `web/src/routes/api/jobs/**`,
  `web/src/lib/jobs-api.ts`, with tests. Done when lint, typecheck, build and web tests pass.
- [x] 4. **Docs.** `docs/technical-design.md`, README row. Done when the full Verify passes.
- [x] 5. **Repair review finding F-111.** Make the HTML walker and `scan` linear and run the
  cleaner off the event loop. Done when a timing test on hostile shapes at the 100,000-character cap passes,
  a differential run against the original gives identical output, and the full Verify passes.
- [x] 6. **Repair review findings F-114 and F-115.** Stop the unterminated-tag regexes crossing a
  `<`, add a timing test over repeated unterminated openers, and correct the thread comment. Done
  when 45 hostile shapes clean in bounded time, a differential run is identical, and the full Verify
  passes.
- [x] 7. **Repair review findings F-116 to F-119.** Possessive tag name, bounded tag scans (a tag
  with more than 1,000 characters of attribute text is not read as a tag), the dropped-block tag
  strip linear, `<` allowed inside a tag again so hidden content stays stripped, the paste cap
  lowered to 100,000 characters, and timing tests that really reach the HTML path. Done when 62
  hostile shapes clean in under a second each and the full Verify passes.

## Files / areas

`engine/src/engine/jobs/*`, `engine/migrations/versions/0008_job.py`, `engine/src/engine/models.py`,
`engine/src/engine/routes/internal.py`, `engine/src/engine/profile/routes.py` (body reader takes a
size), `engine/tests/test_posting_guard.py`, `engine/tests/test_jobs_routes.py`,
`THIRD_PARTY_NOTICES.md`, `web/src/server/jobs/*`, `web/src/server/profile/http.ts` (body cap per
call), `web/src/routes/api/jobs/**`, `web/src/lib/jobs-api.ts`, `web/tests/jobs-*.test.ts`, docs.

## Data / contracts

`engine.job`: `id` uuid pk; `user_id` uuid; `company` text (1 to 120); `title` text (1 to 200);
`location` text null (up to 120); `source_url` text null (up to 2000, http or https only);
`url_key` text null (the URL lowercased in scheme and host, fragment and `utm_*` removed, trailing
slash removed); `dedupe_key` text (lowercase ASCII slug of company and title, with a short hash of
the full text so long or non-Latin names stay distinct); `description` text (cleaned, 1 to 30,000
characters); `status` text (`saved` default, `dismissed`); `flag` text (`ok` or `review`);
`findings` jsonb (counts only: `instructionLike`, `invisibleInWords`, `tagCharacters`,
`invisibleText`, `mixedScriptWords`, `hiddenBlocks`, `hiddenUrls`); `created_at`, `updated_at`.
Unique `(user_id, dedupe_key)` and unique `(user_id, url_key)` where `url_key` is not null.

Routes (bearer token, `X-User-Id`, errors `{code, message}`, every query filters on `user_id`):

- `POST /internal/jobs {company, title, text, location?, url?}` -> 201 job. `text` is the raw
  posting (5 to 100,000 characters, plain or HTML); the stored `description` is the cleaned text
  and must be 1 to 30,000 characters. Body cap 256 KB. 409 `already_exists` for a repeated URL or
  company and title; 422 `limit_reached` at 500 jobs; 422 `validation_failed` otherwise.
- `GET /internal/jobs?status=saved|dismissed` -> list of summaries (no description), newest first;
  no filter returns saved only; an unknown status is 422.
- `GET /internal/jobs/{id}` -> the job with its description.
- `PATCH /internal/jobs/{id} {status}` -> job; `DELETE /internal/jobs/{id}` -> 204.
- A job answers `{id, company, title, location, sourceUrl, status, flag, findings, createdAt}` plus
  `description` on the single read.

The flag is `review` when any of `instructionLike`, `invisibleInWords`, `tagCharacters`,
`invisibleText` or `mixedScriptWords` is above zero; hidden blocks and URLs are context only (as in
the source tool). The flag advises: the job is still stored, and the description is the cleaned text
the later features read. Text is never logged. Pasted text is untrusted data, never instructions.

## Testing

Engine pytest for the cleaner and the routes (including a race on duplicate creates and ownership).
Vitest for the client and proxy. No browser pass: there is no screen in this feature.

## Notes for the AI

Reuse `_clean`, `ApiError`, the row-per-user advisory lock used for track creation, and the web
`forward()`. No new dependencies (standard library only for the cleaner).


<!-- blueprint:completion {"schemaVersion":2,"specBytes":6548,"specSha256":"0cb235c12917a450fe5ec09e0276fe6b1593c420ab8e8e4a5f5770bd9c28aab6","branch":"refs/heads/feature/job-table-and-paste","head":"ac7709094bfe416c2aff5f611c29f40a93eff824","baseRef":"refs/heads/main","baseCommit":"fc000dd382535fc07671404c0a0898746da6a952","sourceTree":"22ab02a5aa2b3c02df25a0dc415b79da97611694","landing":"local-merge","absentOptional":[]} -->

## Findings

_No finding was closed in this build._

Findings of this build: F-111 and F-114 to F-119 were repaired (status fixed, awaiting a later audit to close); F-120 (P2, hidden content survives an opening tag padded past 1,000 characters) and F-121, F-112, F-113 (P3) are open. None is closed, so all are kept in the live ledger with their IDs.

## Independent review

Original passing receipt for checkpoint `ac7709094bfe416c2aff5f611c29f40a93eff824`, copied unchanged:

````markdown
**Status:** passed
**Target commit:** ac7709094bfe416c2aff5f611c29f40a93eff824
**Base commit:** fc000dd382535fc07671404c0a0898746da6a952
**Base ref:** main
**Spec hash:** 0cb235c12917a450fe5ec09e0276fe6b1593c420ab8e8e4a5f5770bd9c28aab6
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-10T16:05:31Z
**Workflow:** continuous
**Check required:** no
**Scope:** current
**Lenses:** quality, security, performance, tests
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-10T17:05:00Z
**Verdict:** passed
**Check result:** not-required

## Handoff

Review the active spec and the complete `<base>..<target>` delta in a fresh
session or isolated subagent without the builder conversation. Run all Audit lenses from scratch.
Run Check when required above. Do not edit product code, accept findings, or
reuse the existing findings as the review scope.
This is the fourth review. Earlier ones found F-111 and F-114 to F-119 in the posting cleaner (quadratic paths, a hidden-content bypass); all were repaired, the last by bounding tag matching (TAG_MAX) and lowering the paste cap to 100,000 characters.

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `shasum -a 256 blueprint/context/current-feature.md`: pass (target, base and spec hash match; only review.md differed)
- `npm run lint`, `npm run typecheck`, `npm test` (177 passed, 1 skipped), `npm run build` (web): pass
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (engine): pass
- `uv run --env-file ../.env pytest -q` (engine): pass (352 passed, 9 skipped)
- Throwaway sweeps at 100,000 characters (about 100 structured shapes, 80 quote/dense-opener shapes, 800 random unit mixes) and hidden-content probes in the reviewer scratchpad: fail (F-120)

## Evidence

- F-116 and F-117 are repaired: long tag names, `<` runs in comments and scripts, and all earlier shapes run in under 0.4 s; the slowest shapes found are dense unterminated openers at 1.0 to 1.5 s (F-121).
- Output unchanged for ordinary pages: 40,000 random tag soups without padding or stray `<` inside tags matched the pre-repair cleaner exactly; `<div hidden <b>` content is stripped again.
- Hidden content survives when an opener is padded past 1,000 characters (spaces, an unquoted value, or many attributes), and a script, style or template with a padded opener leaks its body as visible text (F-120).
- Rest of the delta (ownership scoping, advisory-lock cap and duplicates, `url_key`, counts-only findings, per-call web body cap, migration 0008, the 100,000-character cap) shows no new defect beyond F-112 and F-113.

## Findings

- F-120 (P2, open)
- F-121 (P3, open)

## Remaining risk

- Passed because no P0 or P1 is open; F-120 (P2) is a real hidden-content bypass by padding an opener past 1,000 characters and should be repaired before the feature closes.
- Existing P3 entries F-112 and F-113 remain open.
- No browser pass (none required: no screen in this feature).
````

## Try guide

Skipped: `/check guide` is user-run and was not available to the completing session (the same decision the user made for 3a). Run `/check guide latest` for a walkthrough. The live DeepSeek parse was not run because `.env` had no AI model or key.
