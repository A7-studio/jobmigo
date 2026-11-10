# Feature: Track variants

**From build-plan:** feature 4c
**Build attempt:** 1
**Branch:** feature/track-variants
**Status:** verified

## Goal

A user can keep up to ten named tracks (for example "Flutter and mobile") and mark which of their
confirmed facts each track emphasises. This stores the variant only; nothing generates from it yet.

## Design reference

The Goals board (Jobmigo canvas, `project/Goals.dc.html`, "Step 3 of 4, Make it yours", section
"What are you hoping to find?") shows tracks as a chip row: selected chips are filled, "+ Add your
own" adds one. It is saved to `blueprint/reference/goals.dc.html`. No board shows choosing which facts a
track emphasises. Decision (user, this run): reuse that chip row on `/profile` and add an "Emphasise
for this track" toggle to each confirmed or edited fact in the existing `/profile` look. Deviation to
record: that toggle and the track rename and delete controls have no board.

## In scope

- Engine tables `track` and `track_profile_item` (migration 0006), models, and routes under
  `/internal/tracks`: list, create, rename, delete, emphasise and un-emphasise a fact.
- Web proxy routes `/api/tracks/**`, a typed client, a view model, and the track chip row with
  emphasis toggles on `/profile`.
- Rules: a track name is 1 to 60 characters after collapsing whitespace, unique per user ignoring
  case; at most 10 tracks per user; only a `confirmed` or `edited` fact of the user's latest parsed
  profile can be emphasised; each emphasis change and each rename bumps `variant_version`.
- No plan limit (user decision: add the cap when billing lands).

## Out of scope

Target roles, salary, locations, criteria, dealbreakers and do-not-apply (feature 5); the onboarding
step 3 screen, weekly pace and Telegram; generating anything from a track (features 8 and 11);
reordering tracks; plan limits.

## Build loop

Follow the repository defaults: `workflow.stepReview` and checkpoint commits as configured. Verify
after each step that touches code.

## Build steps

- [x] 1. **Tables and migration.** `engine/migrations/versions/0006_tracks.py` and models `Track`
  and `TrackProfileItem` in `engine/src/engine/models.py`. Done when `alembic upgrade head`
  applies on the dev database, a downgrade then upgrade works, and the engine tests still pass.
- [x] 2. **Engine service, routes and tests.** `engine/src/engine/tracks/` (`models.py`,
  `service.py`, `routes.py`), mounted at `/internal/tracks`; deleting a fact also removes its
  emphasis rows. Done when tests cover each route, ownership (another user's track is `not_found`),
  duplicate and cap errors, validation, emphasis of an unconfirmed fact refused, concurrent edits,
  deleting a track removing its items, deleting a fact removing its emphasis, and the full engine
  Verify passes.
- [x] 3. **Web proxy, client and view model.** `web/src/server/tracks/http.ts`,
  `web/src/routes/api/tracks/**`, `web/src/lib/tracks-api.ts`, `web/src/lib/tracks-view.ts` with
  tests (name check and collapsing, calm copy per code, emphasis set). Done when lint, typecheck,
  build and web tests pass.
- [x] 4. **The track UI on `/profile`.** A "Tracks" section above the facts: chip row (selected
  chip filled, `aria-pressed`), "+ Add a track" inline form, rename and delete (with confirm) for the
  selected track, and an "Emphasise for <track>" toggle (`aria-pressed`) on each confirmed or edited
  fact while a track is selected. Honest empty state (no tracks yet), loading and error states, one
  mutation at a time, focus and live-region rules as on the rest of the page. Done when, in the
  browser against the local engine with a throwaway account and a seeded draft, every action works
  and the console shows no errors.
- [x] 5. **Design check, evidence and docs.** Capture 1440 and 390 wide beside the Goals and Profile
  boards, list each difference against the Deviations, update `docs/technical-design.md` and the
  README status row. Done when each state was seen and the full Verify passes.
- [x] 6. **Free-tier AI providers (user request during the run, outside the track work).** Add
  `gemini`, `groq` and `cloudflare` to the gateway's provider table with env, compose and docs
  entries. Done when `tests/test_ai_config.py` covers them and engine lint and mypy pass. Not
  verified live: no keys for these providers were available.

## Files / areas

`engine/migrations/versions/0006_tracks.py`, `engine/src/engine/models.py`,
`engine/src/engine/tracks/*`, `engine/src/engine/profile/service.py` (cleanup on fact delete),
`engine/src/engine/routes/internal.py`, `engine/tests/test_tracks_*.py`, `web/src/server/tracks/*`,
`web/src/routes/api/tracks/**`, `web/src/lib/tracks-*.ts`, `web/src/routes/_app/profile.tsx`,
`web/src/components/profile/*`, `web/tests/tracks-*.test.ts`, `blueprint/reference/goals.dc.html`,
`docs/technical-design.md`, `README.md`.

## Data / contracts

Tables in schema `engine`:

- `track`: `id` uuid pk, `user_id` uuid, `name` text, `variant_version` int not null default 1
  (check >= 1), `created_at`, `updated_at`; unique index on `(user_id, lower(name))`.
- `track_profile_item`: `id` uuid pk, `user_id`, `track_id` fk to `track` on delete cascade, `kind`
  (check in experience, skill, achievement, project, education), `item_id` uuid (no foreign key: it
  points at one of five tables); unique `(track_id, kind, item_id)`.

Routes (bearer token and `X-User-Id` as elsewhere; body cap 32 KB; every statement filters on
`user_id`; errors are `{code, message}`):

- `GET /internal/tracks` -> `[{id, name, variantVersion, emphasis: [{kind, itemId}]}]`, oldest first.
- `POST /internal/tracks {name}` -> 201 track; 409 `already_exists`; 422 `limit_reached` at 10.
- `PATCH /internal/tracks/{id} {name}` -> track; 404 `not_found`; 409 `already_exists`.
- `DELETE /internal/tracks/{id}` -> 204.
- `PUT /internal/tracks/{id}/items/{kind}/{itemId}` -> track (idempotent); 404 if the fact is not in
  the latest parsed profile; 422 `not_confirmed` if its status is `extracted`.
- `DELETE /internal/tracks/{id}/items/{kind}/{itemId}` -> track (idempotent).

Emphasis rows whose fact no longer exists (a deleted CV cascades its profile) are ignored by the
screen because it only reads emphasis for facts it shows. Mutations lock the track row
(`FOR UPDATE`). Names render as React text only. Nothing logs names.

## Testing

Engine: pytest against the test database for the contracts above. Web: Vitest for the view model and
the API client (each route path and method). Browser pass as in step 4, not kept in the repo.

## Notes for the AI

Reuse the profile module's patterns (`ApiError`, `invalid()`, body reader, row lock). Follow the
`/profile` conventions for focus, live regions and calm copy. Collapse whitespace on the client the
same way as the engine. No new dependencies.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":6844,"specSha256":"bb6d2a53418f3269e663d73767a325a3205e61e386c261d959671b3dbcca5935","branch":"refs/heads/feature/track-variants","head":"f8d60edc9add79c6fbaba8a02e795be175afa8da","baseRef":"refs/heads/main","baseCommit":"0b42dfbf0c5a7590d6d0e32cadc9467476be2d6c","sourceTree":"34d3ab7f10d0e5c6892540a908a8b46bf639441a","landing":"local-merge","absentOptional":[]} -->

## Findings

_No finding was closed in this build._

Findings F-104 (P2) and F-105 to F-107 (P3) from the independent review are open and were not repaired in this build; they are kept in the live ledger with their IDs.

## Independent review

Original passing receipt for checkpoint `f8d60edc9add79c6fbaba8a02e795be175afa8da`, copied unchanged:

````markdown
**Status:** passed
**Target commit:** f8d60edc9add79c6fbaba8a02e795be175afa8da
**Base commit:** 0b42dfbf0c5a7590d6d0e32cadc9467476be2d6c
**Base ref:** main
**Spec hash:** bb6d2a53418f3269e663d73767a325a3205e61e386c261d959671b3dbcca5935
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-10T13:08:30Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-10T13:30:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `shasum -a 256 blueprint/context/current-feature.md`: pass (all match the request; only review.md differed)
- `npm run lint` (web): pass
- `npm run typecheck` (web): pass
- `npm test` (web): pass (163 passed, 1 skipped)
- `npm run build` (web): pass
- `uv run ruff check .` (engine): pass
- `uv run mypy` (engine): pass
- `uv run --env-file ../.env pytest -q` (engine): pass (283 passed, 9 skipped)
- Migration 0006 downgrade then upgrade on the dev database: unavailable (reviewed statically; not run, to avoid changing the shared dev database)

## Evidence

- Every query in `engine/src/engine/tracks/service.py` filters on `user_id`; track rows are locked `FOR UPDATE`, facts are checked against the user's latest profile and `user_id`.
- Creation takes `pg_advisory_xact_lock(hashtext(user_id))` before the count; the same transaction inserts, and a test races creates at the cap.
- Cloudflare URL is built only from a validated account id and the key is read from env and never echoed; `forward()` now answers 204 on an undefined engine result, and the proxy test covers 204 and the track body.
- Migration 0006 creates both tables, the kind check, the unique indexes and cascade, and drops them in reverse.

## Findings

- F-104 (P2, open), F-105 (P3), F-106 (P3), F-107 (P3)

## Remaining risk

- F-104: the track section can get stuck in delete or rename mode after a `not_found`; found by reading, not run in a browser.
- Migration 0006 downgrade and upgrade were not executed by the reviewer.
- Free-tier provider entries (gemini, groq, cloudflare) are not verified live; no keys were available.
- Emphasis orphans (F-106) must be filtered by the future generation features.
````

## Try guide

Skipped: `/check guide` is user-run and was not available to the completing session (the same decision the user made for 3a). Run `/check guide latest` for a walkthrough. The live DeepSeek parse was not run because `.env` had no AI model or key.
