# Feature: Opportunity types

**From build-plan:** feature 34
**Build attempt:** 1
**Status:** verified
**Branch:** feature/34-opportunity-types

## Goal

A saved opportunity is a **job**, a **freelance gig** or an **AI training role**, and so is each
track. A track only checks opportunities of its own type, a new gig or AI training track starts
with sensible preferences, and the type says which document the application kit will write (a
cover letter for a job, a proposal for a gig or an AI training role). Nothing here writes the kit.

## Decisions made with the founder (2026-11-11)

- The type lives on both the job and the track (a track only checks jobs of its own type).
- Creating a track of a type fills starting preferences the person can edit: gig and AI training
  start with work mode remote; job starts empty.
- The type is picked when adding a job (default Job) and can be changed later in the workspace.

## In scope

- Migration `0014_opportunity_kind.py`: `job.kind` and `track.kind`, text, not null, default
  `job`, check in (`job`, `gig`, `ai_training`). Existing rows become `job`.
- Engine: `kind` on job create and on `JobOut`/`JobFull`; `PATCH /jobs/{id}` accepts `status`,
  `kind` or both (at least one); `kind` on track create and on `TrackOut`; starting preferences
  by kind; screening and evaluation only use tracks whose kind equals the job's kind (a wrong
  track on evaluate is a calm 422 `wrong_type`); lists show only matching-kind results. Rows
  made before a type change are kept, so changing back brings them back.
- Web: types and calls carry `kind`; the add-job form has a type choice; the job list row and
  the workspace header show the type; the workspace changes it; the track create form has a type
  choice and each track shows its type; the Fit step shows only tracks of the job's type, with a
  calm "no track of this type" state that links to Profile.
- `opportunityKinds` helper (labels, which document the kit writes) for feature 11 to use.
- Tests; Verify passes.

## Out of scope

The application kit, proposals, per-type evaluation rules or pay units, changing a track's type
after it is created, filtering the Jobs list by type.

## Rules

- A track's type cannot change after creation (delete and re-create), so its saved results stay
  true. A job's type can change; its old results stay stored and hidden until it changes back.
- An unknown type is refused (422); a missing type means `job`.
- No new text is sent to a model.

## Build steps

- [x] 1. Migration `0014`, models, jobs and tracks in/out shapes, create and patch, starting
  preferences, and tests (`test_db.py` head `0014`).
- [x] 2. Screening and evaluation use only same-type tracks; lists filter; tests.
- [x] 3. Web types, calls, handlers pass `kind`; `opportunityKinds` helper; tests.
- [x] 4. Web screens: add-job choice, row and workspace type, track create choice and badge, Fit
  step filter; lint, typecheck, build.
- [x] 5. Verify, independent review (migration, user data), archive, merge.

## Notes for the AI

Keep the one-row-per-job-and-track tables as they are. Do not rewrite stored results when the
type changes. Reuse `_validated`, `not_found` and the existing handler/test patterns.

## Step notes

- Engine: `PATCH /jobs/{id}` now takes `status`, `kind` or both (`JobPatch`); the old name
  `set_status` is kept. A track's type is set only on create (`TrackCreate`); rename still uses
  `TrackIn` (extra fields refused), so a rename cannot change it.
- Screening runs only tracks of the job's type; `list_screens` and `list_evaluations` filter the
  same way, so results made before a type change stay stored but hidden. Evaluating with a track of
  another type is a 422 `wrong_type`.
- Starting preferences: gig and AI training tracks start with work mode remote (`STARTING_WORK_MODES`).
- Web: add-job type choice, row label for non-job types, workspace Type select, track-create type
  choice and chip label, Fit step shows only same-type tracks.
- `kindDocument` (cover letter or proposal) exists for feature 11; nothing uses it yet.
- Verify: engine 736 passed, 10 skipped; ruff, format and mypy pass. Web lint, typecheck and build
  pass; web tests 232 passed, 1 skipped.
- Browser check: pending migration `0014` and an engine restart.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":4294,"specSha256":"0dd4b4702ed67ea2deafbaee1b71e25e6492e3c809b1a5aa75db037bc473bef5","branch":"refs/heads/feature/34-opportunity-types","head":"2fd3b2f36e97bd96d77c396b7262c1b7f7fb8492","baseRef":"refs/heads/main","baseCommit":"3e72a3ee89667c91868ec3a85a02358ad73b6609","sourceTree":"c5c7dbaa5e6c222306599b7e683c84e34f17be31","landing":"local-merge","absentOptional":[]} -->

## Independent review

**Status:** passed
**Target commit:** 2fd3b2f36e97bd96d77c396b7262c1b7f7fb8492
**Base commit:** 3e72a3ee89667c91868ec3a85a02358ad73b6609
**Base ref:** main
**Spec hash:** 0dd4b4702ed67ea2deafbaee1b71e25e6492e3c809b1a5aa75db037bc473bef5
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T17:45:21Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T17:50:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Handoff

Review the active spec and the complete `main..target` delta in a fresh
session or isolated subagent without the builder conversation. Run all Audit lenses from scratch.
Do not edit product code, accept findings, or reuse the existing findings as the review scope.

## Commands

- `uv run --env-file ../.env pytest -q` on test_opportunity_kind, test_db, test_job_screen_routes, test_evaluation_routes, test_evaluating, test_jobs_routes, test_tracks_routes (engine/): pass (88 passed)
- `npm test` (web/): pass (232 passed, 1 skipped)
- Temporary probe test (removed): migration 0013 with existing job and track rows upgraded to 0014 (both become `job`), downgrade to 0013 with a `gig` row removes both columns, upgrade again: pass; PATCH and track-create edge cases: pass

## Evidence

- Migration 0014: not null, default `job`, check constraints on both tables, existing rows become `job`, downgrade clean; model constraints match the migration.
- `JobPatch`: empty body, unknown or null-only kind, extra fields refused (422); other users' jobs 404; status and kind change together. `{"status": "x", "kind": null}` treats the null as absent (accepted, kind unchanged).
- Tracks: `kind` only on `TrackCreate`; rename (`TrackIn`) and preferences (`extra=forbid`) refuse a `kind`; gig and AI training start remote; a null kind is refused.
- Screening, `list_screens`, `evaluate_job` (422 `wrong_type`, checked before the cache) and `list_evaluations` all filter by the job's type; every other `Track`, `JobScreen` and `Evaluation` use in the engine is by id and owner, or the one-row-per-pair upsert. Cache and rules keys do not need the type: a track's type is fixed and the job text does not change, so results hidden and restored on a type change stay current.
- Same posting added again with another type returns the existing 409, not a second job.
- Web: add-job radio, row label, workspace Type select updates the workspace cache and invalidates `fit-evaluations` and `jobs`; track-create choice shown only when adding; labels render as text.

## Findings

- F-174 (P3), F-175 (P3)

## Remaining risk

- A screen or evaluation in flight when the job's type changes is saved against the old type's track and then hidden; an in-flight evaluate can return 422 `wrong_type` after a concurrent type change, shown as a generic message. Low impact; not probed.
- Web behavior was reviewed from code and unit tests; no browser run (the migration was not applied to a dev database and the engine was not restarted).
- Existing open findings F-168 to F-173 belong to earlier work and were not re-reviewed here.
