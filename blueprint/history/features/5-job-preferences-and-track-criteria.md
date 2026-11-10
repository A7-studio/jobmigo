# Feature: Job preferences and track criteria

**From build-plan:** feature 5
**Build attempt:** 1
**Branch:** feature/job-preferences-and-track-criteria
**Status:** verified

## Goal

Each track holds the user's job preferences: target roles, salary floor, work modes, places,
eligibility, must-have, important and nice-to-have criteria, dealbreakers and a do-not-apply list.
Stored and editable only; nothing evaluates against them yet (features 29 and 8 read them).

## Design reference

No board shows per-track preferences. The Goals board ("Make it yours") shows the wording and the
chip and field look for the global version: "Lowest salary you would consider", "Where can you
work?", "Anything that is a firm no?" with "Optional. Migo skips these jobs before spending any of
your credits." (`blueprint/reference/goals.dc.html`). Decision (user, this run): a Preferences panel
for the chosen track inside the "Your tracks" card on `/profile`, using that wording and the
existing `/profile` field styles. Deviation to record: the panel, the criteria groups and the
do-not-apply field have no board.

## In scope

- Migration 0007: preference columns on `track`.
- Engine: preferences in the track list and create/rename answers, and
  `PATCH /internal/tracks/{id}/preferences` (partial, validated, `extra=forbid`).
- Web: proxy `PATCH /api/tracks/{id}/preferences`, client, view model, and the panel on `/profile`.
- Rules below; one mutation at a time, calm copy, focus and live-region rules as on the page.

## Out of scope

Evaluating jobs, applying dealbreakers, the onboarding step 3 screen, weekly pace, Telegram,
structured (typed) dealbreakers (user decision: plain-text rules), plan limits.

## Build steps

- [x] 1. **Engine.** `engine/migrations/versions/0007_track_preferences.py`, columns on `Track`,
  `engine/src/engine/tracks/preferences.py` (validation), service `patch_preferences`, route,
  `TrackOut.preferences`. Done when engine tests cover defaults, partial merge, each bound,
  ownership, the 32 KB cap, unknown fields, that preferences do not change `variantVersion`, and the
  full engine Verify passes.
- [x] 2. **Web proxy, client and view model.** `handlePreferences`, route
  `web/src/routes/api/tracks/$id/preferences.ts`, `patchPreferences`, form helpers in
  `web/src/lib/tracks-view.ts` (`toPrefsForm`, `fromPrefsForm` with the same bounds and whitespace
  collapsing, only changed fields sent) with tests. Done when lint, typecheck, build, tests pass.
- [x] 3. **The panel.** A "Preferences" disclosure for the chosen track in the Your tracks card:
  labelled fields, errors tied to inputs, Save and Cancel, saved state announced. Done when, in the
  browser with a throwaway account, a save round-trips, each validation error shows once beside its
  field, focus rules hold, 390 wide has no horizontal scroll and the console is clean.
- [x] 4. **Docs and evidence.** `docs/technical-design.md`, README row; list differences against
  the Goals wording. Done when the full Verify passes.

## Files / areas

`engine/migrations/versions/0007_*.py`, `engine/src/engine/models.py`,
`engine/src/engine/tracks/*`, `engine/tests/test_tracks_prefs.py`, `web/src/server/tracks/http.ts`,
`web/src/routes/api/tracks/$id/preferences.ts`, `web/src/lib/tracks-*.ts`,
`web/src/components/profile/tracks.tsx`, `web/src/components/profile/preferences.tsx`,
`web/src/routes/_app/profile.tsx`, `web/tests/tracks-*.test.ts`, docs.

## Data / contracts

Columns on `engine.track` (all optional; empty list or null means "no preference"):

| Column | Type | Bounds |
| --- | --- | --- |
| `target_roles` | text[] not null default `{}` | up to 10 items, each 1 to 80 characters |
| `salary_floor` | int null | 0 to 10,000,000 |
| `currency` | text null | 3 uppercase ASCII letters; required when `salary_floor` is set |
| `work_modes` | text[] not null default `{}` | subset of `remote`, `hybrid`, `onsite`, no repeats; empty = any |
| `locations` | text[] not null default `{}` | up to 10 items, each 1 to 80 characters |
| `eligibility` | text null | up to 500 characters |
| `criteria` | jsonb not null default `[]` | up to 30 `{label (1 to 120), weight: must|important|nice}`, labels unique ignoring case |
| `dealbreakers` | jsonb not null default `[]` | up to 10 strings, each 1 to 120 characters (plain-text rules) |
| `do_not_apply` | text[] not null default `{}` | up to 50 companies, each 1 to 80 characters |

Text is cleaned like profile facts (control characters dropped, whitespace collapsed); list items
are unique ignoring case (duplicates are `validation_failed`, not silently merged). Check
constraints in the database mirror the enums and the currency shape.

`PATCH /internal/tracks/{id}/preferences` with camelCase keys (`targetRoles`, `salaryFloor`,
`currency`, `workModes`, `locations`, `eligibility`, `criteria`, `dealbreakers`, `doNotApply`) merges
the keys sent over the stored values, validates the whole result, returns the track. Empty body or
unknown key: 422 `validation_failed`. Another user's track: 404 `not_found`. The track row is locked
for the change. `variantVersion` is not changed (preferences are criteria, not the profile variant);
`updated_at` is. `TrackOut.preferences` carries all nine fields in camelCase.

## Testing

Engine pytest as above. Vitest for the form helpers (bounds, collapsing, diff-only body, criteria
grouping) and the client and proxy (path, method, 401, 404, cap). Browser pass as in step 3.

## Notes for the AI

Reuse `_clean`, the body reader and the row lock. Multi-value fields are one-per-line textareas
(the bullets pattern on the profile form); criteria are three textareas by weight. No new
dependencies. Names and text are never logged.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":5730,"specSha256":"ce2d02fa238c4d2173bfbd7f293cac1876b63534df4807d1e2b9529356de7f38","branch":"refs/heads/feature/job-preferences-and-track-criteria","head":"797a57ca6a14dcecd4a679efdf01013ec60fb39b","baseRef":"refs/heads/main","baseCommit":"d04f8548b112c63e11d49fa4180caabf64e123cf","sourceTree":"9bcd3ca4007b9ad9bdaae43f8764c533dd009624","landing":"local-merge","absentOptional":[]} -->

## Findings

_No finding was closed in this build._

Findings of this build: F-104 and F-105 were repaired (status fixed, awaiting a later audit to close); F-106 to F-110 (P3) are open. None is closed, so all are kept in the live ledger with their IDs.

## Independent review

Original passing receipt for checkpoint `797a57ca6a14dcecd4a679efdf01013ec60fb39b`, copied unchanged:

````markdown
**Status:** passed
**Target commit:** 797a57ca6a14dcecd4a679efdf01013ec60fb39b
**Base commit:** d04f8548b112c63e11d49fa4180caabf64e123cf
**Base ref:** main
**Spec hash:** ce2d02fa238c4d2173bfbd7f293cac1876b63534df4807d1e2b9529356de7f38
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-10T13:19:49Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-10T13:22:28Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `shasum -a 256 blueprint/context/current-feature.md`: pass (target, base and spec hash match; only review.md differed)
- `npm run lint` (web): pass
- `npm run typecheck` (web): pass
- `npm test` (web): pass
- `npm run build` (web): pass
- `uv run ruff check .` (engine): pass
- `uv run mypy` (engine): pass (75 files)
- `uv run --env-file ../.env pytest -q` (engine): pass (314 passed, 9 skipped)

## Evidence

- Engine preferences: merge-then-validate under the track row lock (`_locked` uses FOR UPDATE, ownership in the query, 404 before 422), `extra=forbid` with alias-only names, strict `salaryFloor`, uniqueness by casefold, input never echoed (`_validated` drops the pydantic error), migration check constraints match the pydantic enum, currency and salary rules, arrays and JSONB reassigned whole so changes persist.
- Web form bounds equal the engine's (10/80, 10/80, 10/120, 50/80, 30/120, 500, 10,000,000); body holds only changed keys; an unchanged form closes without a request; criteria uniqueness is checked across all three weights.
- F-104 fix confirmed by reading: the effect in `tracks.tsx` resets `mode` to idle when `selected` disappears (except while adding); `not_found` refreshes the list.
- F-105 fix confirmed: `re.fullmatch(r"[A-Za-z0-9]+")` and a test with a non-ASCII id (`test_ai_config.py`).
- Copy says jobs will be checked "once evaluation arrives"; docs state nothing evaluates yet. Focus moves into the panel on open, to the first invalid field on error, and back to the Preferences button on close; server errors use role=alert.
- Not run in a browser by this reviewer.

## Findings

- F-108 (P3, open), F-109 (P3, open), F-110 (P3, open). No P0 or P1.

## Remaining risk

- Component behaviour (focus, live regions, mode reset) is covered only by reading and the builder's browser pass, not an automated test (see F-107).
- Pre-existing open P3 findings F-102, F-103, F-106, F-107 are unchanged.
````

## Try guide

Skipped: `/check guide` is user-run and was not available to the completing session (the same decision the user made for 3a). Run `/check guide latest` for a walkthrough. The live DeepSeek parse was not run because `.env` had no AI model or key.
