# Feature: Profile fact edit and confirm routes (engine)

**From build-plan:** feature 4a
**Build attempt:** 1
**Branch:** feature/profile-fact-edit-and-confirm-routes-engine
**Status:** verified

## Goal

Let the signed-in user act on the profile draft the engine built from their CV: correct a fact,
confirm it, add one the parse missed, delete a wrong one, or confirm everything at once, with
every change tracked by the fact's `status` and a profile `version` that changes whenever the
profile does. The profile is the user's **latest parsed draft** (decided with the user).
Evaluations and generated documents (later features) may only cite `confirmed` or `edited` rows
and key their caches on `version`. No screen here (4b) and no tracks (4c).

## In scope

1. Migration `0005`: `profile.version` (int, default 1) and `profile.updated_at`.
2. Engine routes under `/internal/profile` (router-level auth already applies):
   `GET /internal/profile`; `PATCH /internal/profile` (headline, summary);
   `POST /internal/profile/items/{kind}` (add); `PATCH /internal/profile/items/{kind}/{id}`;
   `POST /internal/profile/items/{kind}/{id}/confirm`; `DELETE /internal/profile/items/{kind}/{id}`;
   `POST /internal/profile/confirm-all`. Kinds: `experience`, `skill`, `achievement`,
   `project`, `education`.
3. Web API routes forwarding each for the session user: `/api/profile` (GET, PATCH),
   `/api/profile/confirm-all` (POST), `/api/profile/items/$kind` (POST),
   `/api/profile/items/$kind/$id` (PATCH, DELETE), `/api/profile/items/$kind/$id/confirm` (POST),
   with kind and UUID checks before any engine call and a body size limit.
4. Docs: `docs/technical-design.md`, `docs/database-design.md`.

## Out of scope

- The review screen (4b), tracks, variants and `TrackProfileItem` (4c), merging several CVs into one
  profile, carrying confirmed facts to a new CV's draft, evidence references, undo or history,
  reordering rows, and any model call.

## Build loop

`blueprint/config.json`: `stepReview: feature`, `checkpointCommits: disabled`; Continuous Mode.
Independent review is required (personal data, a migration, ownership boundaries).

## Build steps

- [x] 1. **Version column and the profile read.** Alembic `0005`; `Profile.version` and
  `updated_at` in `models.py`; `profile_service.get_profile` returns the user's latest parsed
  draft (newest `cv_file.created_at` with `parse_status = 'parsed'`, owner-filtered in the
  statement) in the existing draft shape plus `version`; `GET /internal/profile`. Done when tests
  prove: upgrade and downgrade work; a new draft starts at version 1; the latest of two parsed
  CVs wins; a user with no parsed draft, and another user's draft, get the same 404 body; the
  existing `GET /internal/cv/{id}/profile` still works (`uv run pytest tests/test_profile_read.py
  tests/test_db.py`).
- [x] 2. **Edit rules and the item service.** `engine/src/engine/profile/` (`models.py` with the
  input models reusing the bounds and cleaning from `cv/parse.py`, `service.py`). Rules in
  Data / contracts. Done when DB-backed tests prove each rule below, one test per rule:
  add, patch (status becomes `edited`, no-op patch changes nothing and does not bump the
  version), confirm (`extracted` to `confirmed`; others unchanged), delete (and an achievement
  whose experience is deleted keeps its text with no link), confirm-all, limits, duplicate skill,
  achievement link to another profile's experience refused, every mutation bumping `version` by
  exactly one only when something changed, and the owner scope on every statement
  (`uv run pytest tests/test_profile_edit.py`).
- [x] 3. **Engine routes.** `profile/routes.py` included under `/internal/profile`; stable
  errors. Done when route tests through the ASGI app prove statuses and bodies in Data /
  contracts, one identical 404 body for a missing, malformed, foreign or older-draft id,
  `422 validation_failed` for bad bodies with no echo of the input, and the bearer token on every
  route (`uv run pytest tests/test_profile_routes.py`).
- [x] 4. **Web routes and docs.** `web/src/server/profile/http.ts` handlers (session first, kind
  and id checks, a 32 KB body cap, engine 4xx codes passed through, 5xx as `engine_unavailable`),
  the route files, regenerated `routeTree.gen.ts`, tests, and the two docs. Done when Vitest
  proves 401 without a session, kind and UUID checks before any engine call, the body cap, the
  method and path forwarded for each of the seven calls, and error mapping; the full Verify
  passes (`npm test`, then the Verify command).

- [x] 5. **Repair the review's findings F-85 to F-89.** Lock the profile row for every mutation
  (serialises edits and stops stale reads, lost updates, unguarded confirms and count races);
  fold skill names the same way on both sides of the duplicate check; catch `RecursionError` in
  the body parser; cap the body while it streams in the engine and the web handler; add the
  missing tests. Done when the concurrent-edit tests pass with the lock (and three fail without
  it), the new route and handler tests pass, and the full Verify passes.

## Files / areas

`engine/migrations/versions/0005_profile_version.py`, `engine/src/engine/models.py`,
`engine/src/engine/profile/{__init__,models,service,routes}.py`,
`engine/src/engine/routes/internal.py`, `engine/tests/test_profile_{read,edit,routes}.py`,
`engine/tests/test_db.py`, `web/src/server/profile/http.ts`, `web/src/routes/api/profile/**`,
`web/src/routeTree.gen.ts`, `web/tests/profile-http.test.ts`, `web/tests/profile-routes.test.ts`,
`docs/technical-design.md`, `docs/database-design.md`.

## Data / contracts

**Statuses.** `extracted` (from the parse), `confirmed` (the user said it is right, unchanged),
`edited` (the user changed it, or added it). Generated work may cite `confirmed` and `edited`.

**Rules.**
- PATCH with at least one known field; unknown keys refused; a patch that changes no value is a
  no-op (200, same body, no version bump). A real change sets `status = edited` and bumps `version`.
- Confirm: `extracted` becomes `confirmed` (version bump); `confirmed` and `edited` are returned
  unchanged. Confirm-all does that for every `extracted` row and returns `{confirmed, version}`;
  with none to confirm it returns `confirmed: 0` and does not bump.
- Add: status `edited`, `position` after the last row of that kind, bumps `version`. Limits per
  kind are the parse limits (`cv/limits.py`); over the limit is `422 limit_reached`. A skill with a
  name already present (case-insensitive) is `409 already_exists`.
- Delete: removes the row (`204`), bumps `version`; an achievement linked to a deleted experience
  keeps its text with `experienceId: null` (existing foreign key).
- `achievement.experienceId`, when given, must be an experience of the same profile and user,
  else `422 validation_failed`.
- Field bounds, date pattern (`YYYY` or `YYYY-MM`) and text cleaning are the parse rules.
- Headline and summary have no status; changing them bumps `version`.

**Bodies** (camelCase, `extra` forbidden): experience `{company, role, start, end, isCurrent,
bullets}`; skill `{name}`; achievement `{text, experienceId}`; project `{name, description}`;
education `{institution, qualification, start, end}`; profile `{headline, summary}`.

**Responses.** The profile is the existing draft body (`id`, `cvId`, `headline`, `summary`,
`experiences[]`, `skills[]`, `achievements[]`, `projects[]`, `education[]`, each row with
`status`) plus `version`. An item is its row object. Errors `{code, message}` with `not_found` 404,
`validation_failed` 422, `limit_reached` 422, `already_exists` 409.

**Trust and tenancy.** The user id comes only from the engine's authenticated header. Every
statement filters on `user_id` and on the profile being that user's latest parsed draft; an item
of an older draft is `not_found`. The version bump and the row change share one transaction. No
field text is logged or placed in an error message.

## Testing

pytest against the real test database (no network, no model); Vitest handler tests with injected
`fetchFn`. No browser tests (no UI).

## Notes for the AI

- Reuse `cv/parse.py` annotated types for bounds; put shared bits where both can import them
  rather than copying the limits. Follow `cv/parse_service.py` for session and statement style.
- Do not touch `cv_file` rows or the parse flow. Keep `GET /internal/cv/{id}/profile` working.
- The plan was split into 4a, 4b and 4c with the user's approval; the overview line was updated
  with it and stays under 20,000 bytes.

## Open questions

None.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":8609,"specSha256":"a8966e988262178af2335faa4e9c03b3b352865b3b00c1482e610ac670e8f36a","branch":"refs/heads/feature/profile-fact-edit-and-confirm-routes-engine","head":"52985e47baceb473347334cd9430b5e55aafa5c1","baseRef":"refs/heads/main","baseCommit":"75c4c622ff8f2cc2a258c1983bb45a419040178c","sourceTree":"4b84e0109dbd3c3c23bb8ae8527de6c3b4157c34","landing":"local-merge","absentOptional":[]} -->

## Findings

### 4a/F-85 [P2] closed - Profile mutations are unserialized read-modify-write, so concurrent edits lose updates and break the limit and duplicate checks

**File:** engine/src/engine/profile/service.py:150 (patch_profile), :233 (patch_item), :264 (confirm_item), :189 (add_item)
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality, security)
**Why it matters:** Every mutation reads the profile or row with a plain SELECT, decides in Python, and writes later; the only lock taken is the row lock of the final `UPDATE profile` (the version bump), which comes after the decision. (1) `patch_item` and `patch_profile` write every merged column, not just the changed ones: two tabs editing `role` and `bullets` of one experience (or `headline` and `summary`) read the same row, and the later commit silently reverts the other edit while the version still bumps twice. (2) `confirm_item` sets `status = confirmed` with no `status = 'extracted'` guard, so a confirm that raced an edit overwrites `edited` with `confirmed` on a changed fact. (3) `add_item` counts then inserts, and checks duplicate skills then inserts, with no unique index on `(profile_id, lower(name))`, so two concurrent adds both pass the check: the limit can be exceeded and two "Flutter" rows can exist. (4) A patch that races a delete of the same row raises SQLAlchemy `StaleDataError` and surfaces as an unhandled 500. The spec asked for exactly one bump per real change and a duplicate/limit rule; none of this is asserted under concurrency.
**Suggested fix:** Take `SELECT ... FOR UPDATE` on the profile row at the start of every mutating transaction (it is already the thing each one bumps), which serializes edits per profile and makes the count, duplicate, no-op and status decisions safe; guard confirm with `WHERE status = 'extracted'`. Add a test that runs two concurrent edits through two sessions.
**Resolution:** Fixed: every mutation locks the profile row (`SELECT ... FOR UPDATE OF profile`) before it reads, so edits to one profile run one at a time and none works from a stale read; tests run concurrent edits, a confirm racing an edit, concurrent adds of one skill and past the limit, and a patch racing a delete (three of them fail without the lock).
Closed 2026-11-10 by /audit independent (target 52985e4): `latest_profile(lock=True)` takes `FOR UPDATE OF profile` before every read in all six mutations; every error path leaves the `async with AsyncSession` block, which rolls back and frees the lock; lock order (profile, then children) matches the CV delete cascade (cv_file, profile, children) and a new parse touches only `cv_file` and a new profile, so no cycle. Removing the lock in a scratch copy makes three concurrent tests fail on three runs (duplicate add, limit, patch vs delete). Two of the new tests do not discriminate (F-90); a narrow post-commit window remains (F-91).

### 4a/F-86 [P3] closed - The duplicate-skill check compares `lower()` in Postgres with Python `casefold()`, so it is asymmetric for non-ASCII names

**File:** engine/src/engine/profile/service.py:129
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The query is `func.lower(Skill.name) == name.casefold()`. `casefold` folds more than `lower` (for example `ß` becomes `ss`), so an existing "Straße" does not match a new "STRASSE" or "strasse" (SQL side `straße` vs `strasse`), while an existing "STRASSE" does match a new "Straße". Postgres `lower` also depends on the database collation. The spec says case-insensitive, and the test covers ASCII only.
**Suggested fix:** Compare the same normalisation on both sides: fetch the profile's skill names (at most the skill limit) and compare `casefold()` in Python, or store and compare a casefolded key; add a non-ASCII case to the test.
**Resolution:** Fixed: the duplicate check loads the profile's skill names and compares them in Python with `casefold()` on both sides; test with "Straße" and "STRASSE".
Closed 2026-11-10 by /audit independent: `_duplicate_skill` loads the profile's skill names under the lock and compares `casefold()` on both sides; the Straße/STRASSE test passes.

### 4a/F-87 [P3] closed - A deeply nested JSON body inside the 32 KB cap gives an unhandled 500 in the engine

**File:** engine/src/engine/profile/routes.py:25
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** `_body` catches only `ValueError` from `request.json()`. `json.loads` raises `RecursionError` (not a `ValueError`) for nesting of a few thousand levels, which fits in 32 KB (confirmed with `{"a":` plus 20000 `[`). The route then returns the framework 500 instead of the stable 422 `validation_failed`, and logs a traceback. The web handler's `JSON.parse` accepts the same body and forwards it, so the user sees `engine_unavailable`. Needs a signed-in user, so it is a correctness and noise issue, not an exposure.
**Suggested fix:** Catch `RecursionError` with `ValueError` in `_body`, and add a route test with a deeply nested body.
**Resolution:** Fixed: `_body` catches `RecursionError` with the JSON errors; test with 20,000 levels of nesting returns 422.
Closed 2026-11-10 by /audit independent: `_body` catches `(ValueError, RecursionError)`; the 20,000-level test passes. Invalid UTF-8 is a `ValueError` subclass, so it is covered too.

### 4a/F-88 [P3] closed - Several rules have no test: older-draft patch and delete, foreign link on patch, other kinds' limits, the content-length cap path, and 401 before the kind check

**File:** engine/tests/test_profile_edit.py:296, web/tests/profile-http.test.ts:98
**Found:** 2026-11-10 by /audit independent (scope: current; lens: tests)
**Why it matters:** The older-draft test exercises `confirm_item` only, not patch or delete; the foreign-experience link is tested on add but not on `PATCH achievement`; the limit is tested for skills only (via a patched constant); the no-op test covers skills only; no test sends two concurrent edits (F-85). In the web tests the "over the cap" case sends a real body but a `Request` built from a string has no `content-length` header, so the declared-length branch is never run; and no test sends an invalid kind or id without a session to prove 401 comes first.
**Suggested fix:** Parametrize the older-draft and foreign-link tests over patch and delete, add a no-op test for a multi-field kind, add a content-length case with an explicit header, and one 401-with-bad-kind case.
**Resolution:** Fixed: added tests for patch and delete of an older draft's item, a foreign achievement link on patch, the limit for every kind, the web Content-Length branch, a streamed oversize body, and 401 before an invalid kind or id.
Closed 2026-11-10 by /audit independent: the listed cases exist and pass (older-draft patch and delete, foreign link on patch, every kind's limit, Content-Length and streamed cap in web, 401 before bad kind). The two concurrency tests that were meant to prove F-85's lost-update and confirm-race points are weaker than claimed (F-90).

### 4a/F-89 [P3] closed - The 32 KB cap is applied after the whole body is buffered

**File:** engine/src/engine/profile/routes.py:21, web/src/server/profile/http.ts:49
**Found:** 2026-11-10 by /audit independent (scope: current; lens: performance)
**Why it matters:** The engine calls `request.body()` and then checks the length, and the web handler checks `content-length` only when the header is present, otherwise reads `request.text()` in full. A chunked body without a length is read completely before refusal. Bounded in practice by the server and the session requirement, so low impact.
**Suggested fix:** Check `content-length` in the engine too, and read the stream with a running byte count that stops at the cap.
**Resolution:** Fixed: the cap is checked from Content-Length and again while the body streams in, in the engine and in the web handler; tests send an oversized streamed body with no length header.
Closed 2026-11-10 by /audit independent: engine checks the header then counts while streaming; web checks the header, counts per chunk, cancels the reader and throws before buffering more; the streamed oversize test passes.

The other findings of this build (F-90 to F-92, all P3) are unresolved and stay in the live ledger with their IDs.

## Independent review

Original passing receipt for checkpoint `52985e47baceb473347334cd9430b5e55aafa5c1`, copied unchanged:

````markdown
**Status:** passed
**Target commit:** 52985e47baceb473347334cd9430b5e55aafa5c1
**Base commit:** 75c4c622ff8f2cc2a258c1983bb45a419040178c
**Base ref:** main
**Spec hash:** a8966e988262178af2335faa4e9c03b3b352865b3b00c1482e610ac670e8f36a
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-10T12:04:59Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-10T12:30:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `cd web && npm run lint`: pass
- `cd web && npm run typecheck`: pass
- `cd web && npm test`: pass (135 passed, 1 skipped)
- `cd web && npm run build`: pass
- `cd engine && uv run ruff check .`: pass
- `cd engine && uv run ruff format --check .`: pass
- `cd engine && uv run mypy`: pass
- `cd engine && uv run --env-file ../.env pytest -q`: pass (271 passed, 9 skipped)
- Scratch copy of `engine/` outside the repo with the `FOR UPDATE` removed, `pytest tests/test_profile_edit.py` three times: three tests fail each time, two concurrency tests still pass (F-90)

## Evidence

- Preconditions confirmed: HEAD equals the target, merge base with `main` equals the base, spec hash matches, only `review.md` and `findings.md` differ.
- Full `git diff 75c4c62..52985e4` reviewed: engine profile service, routes and models, migration 0005, `load_draft` refactor, web handlers, routes and client change, and the new tests.
- Every statement in `profile/service.py` filters on `user_id` (and profile id); bodies use `extra="forbid"` with no field alias for status, ids or version, so mass assignment is refused; errors never carry input.
- Row lock: taken first in every mutation; all exits leave the `async with AsyncSession` block, which rolls back; lock order matches the CV delete cascade and a new parse, so no deadlock cycle found; no-op returns without a bump; one `_bump` per real change under the lock.
- Body caps: header then streamed count in the engine and in the web handler, with reader cancel; `RecursionError` handled.
- Migration 0005 adds a NOT NULL column with a constant default and a check, with a downgrade; the schema tests pass.
- F-85 to F-89 re-examined against the code and closed.

## Findings

- New: F-90 (P3, open), F-91 (P3, open), F-92 (P3, unverified)
- Closed: F-85, F-86, F-87, F-88, F-89
- No P0 or P1 finding is open or fixed

## Remaining risk

- No end-to-end run through the built web server for these routes.
- Migration 0005 was not run against a populated database.
- No UI exists for these routes yet.
- Two concurrency tests do not prove the lock (F-90); a delete racing a write can still give a 500 or 404 after commit (F-91).
````

## Try guide

Skipped: `/check guide` is user-run and was not available to the completing session (the same decision the user made for 3a). Run `/check guide latest` for a walkthrough. There is no UI for these routes yet (feature 4b), so there is nothing to try in a browser.
