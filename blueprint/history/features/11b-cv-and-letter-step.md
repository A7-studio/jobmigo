# Feature: CV and letter step in the job workspace

**From build-plan:** feature 11b
**Build attempt:** 1
**Status:** verified
**Branch:** feature/11b-cv-and-letter-step

## Goal

The CV and letter tab of `/jobs/$jobId` shows the kit written by 11a for one track: the CV,
the cover letter or proposal, and answers to application questions. The person reads it next to the
fact check, fixes or removes each flagged statement in one click, switches between saved versions,
and can write the kit again. Export is 11c and is not built here.

## Decisions made with the founder (2026-11-11)

- A flagged statement can be **removed or edited**; either saves a new version and the whole
  document is checked again by the same code, so an edit that adds an untraceable number is
  flagged too. (Two engine routes, below.)

## Design

- **Engine edit route:** `PATCH /internal/jobs/{id}/kits/{kitId}` with
  `{ "path": "entries.1.bullets.2", "action": "edit" | "remove", "text"?: string }`.
  Paths are the ones the fact check already names: `summary`, `paragraphs.N`, `answers.N`,
  `entries.N`, `entries.N.bullets.M`. `remove` works on `entries.N`, `entries.N.bullets.M` and
  `paragraphs.N` (never the last paragraph); `summary` and answers can only be edited. `edit`
  needs `text` (cleaned, not empty, within the block's length cap).
- **A new version, never an overwrite.** The patch is applied to a copy of the version's content
  and saved as the next version of that document. Only the latest version can be patched
  (`409 not_latest` otherwise). The whole document is checked again from its stored sources: each
  source is found again by fact id among the facts of the version's own profile that are still
  confirmed or edited; a source that is gone is dropped, so its block is flagged `no_source`.
- Edited blocks carry `edited: true` and the fact check lists their paths in `edited`. An edited
  version's cache key never equals a written one, so writing the kit again makes a fresh version
  and keeps the edited one.
- **Screen:** track picker for tracks of the job's type, the states not started, working, ready,
  stale, failed with retry and no-track, optional questions (up to 5) before writing, document
  switcher, the fact check summary with a list of what needs the person, flagged blocks with
  Edit and Remove, the facts behind a block on demand, a version picker (older ones read-only).
  Export is shown as not built yet.
- Wording: "trace to a confirmed fact" and "needs you", never a score or a percentage. Text from
  the model and the person is shown as text only.

## In scope

- Engine: `kit_edit.py` (pure patch and recheck), `kitting.edit_kit`, the route, tests.
- Web: proxy handler and route, client function and types, `kit-view.ts` helpers, `kit-step.tsx`,
  wiring into `job-workspace.tsx`, tests; lint, typecheck, build; a browser check when possible.

## Out of scope

Export (11c), writing the kit in the background, changing which facts a block cites, deleting a
version, comparing versions side by side.

## Build steps

- [x] 1. Engine `kit_edit.py`, `edit_kit`, the route and tests.
- [x] 2. Web client, handler, route, `kit-view.ts` and tests.
- [x] 3. `kit-step.tsx` and the workspace wiring; lint, typecheck, build.
- [x] 4. Verify, browser check, independent review, archive, merge.

## Notes for the AI

Reuse `kit_check.check_block`, `kit_write` block shapes (`text`, `sources[{label,kind,id}]`,
`flags`, `numbers`) and `eval_evidence.load_facts`. Mirror `FitStep` for tracks, states and copy.
Do not give the person a score. Keep text-only rendering.

## Step notes

- Engine: `kit_edit.apply_edit` (path, action and length rules; never changes its input) and
  `recheck` (every block checked again; sources found again by fact id among the version's own
  profile facts that are still confirmed or edited; the `edited` flag and the `omitted` count are
  kept). `kitting.edit_kit` takes the same per-job-and-track lock and advisory lock as writing,
  accepts only the latest version (`409 not_latest`), saves the next version with a cache key that
  starts `edit:` so writing again makes a fresh version and keeps the edited one, and prunes to
  10. Stored content with missing parts is refused or checked, never a 500.
- Web: `editKit`, `handleJobKitEdit`, the route `/api/jobs/$id/kits/$kitId` (file
  `kits_.$kitId.ts`), `kit-view.ts` (words, ordering, `blocksOf`, `needsYou`, `checkSummary`,
  `checkQuestions`, `kitCopy`, `factLine`) and `kit-step.tsx`. The Fit step now reads tracks under
  `['tracks']` like Profile, which closes F-175.
- Statements show text only. Sources show the fact's one-line wording read from the person's
  profile by id; a fact that is gone says so.
- Not done: export (11c); the screen was not seen in a browser (it needs migration `0015`, an
  engine restart and either a real model or a seeded kit).
- Verify: engine 867 passed, 11 skipped; ruff, format and mypy pass. Web lint, typecheck and build
  pass; web tests 248 passed, 1 skipped.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":5024,"specSha256":"d4d8605e97d26f23eefeefa8dad072d4c2d5b1a0f8e5833bb1d17a0288f8a2d7","branch":"refs/heads/feature/11b-cv-and-letter-step","head":"9e2130961f653ad4630d415cd856ea90e4c06c81","baseRef":"refs/heads/main","baseCommit":"2f03f2fecd83b8e6dd7f9073493edfc30b5a474e","sourceTree":"c5c1b38e82f880e89477626cfe0abd59b949bbe0","landing":"local-merge","absentOptional":[]} -->

## Independent review

**Status:** passed
**Target commit:** 9e2130961f653ad4630d415cd856ea90e4c06c81
**Base commit:** 2f03f2fecd83b8e6dd7f9073493edfc30b5a474e
**Base ref:** main
**Spec hash:** d4d8605e97d26f23eefeefa8dad072d4c2d5b1a0f8e5833bb1d17a0288f8a2d7
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T19:10:00Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T20:00:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `cd engine && uv run --env-file ../.env pytest -q tests/test_kit_edit.py tests/test_kitting.py tests/test_kit_routes.py tests/test_kit_check.py tests/test_kit_write.py tests/test_db.py`: pass (126 passed)
- `cd web && npm test`: pass (248 passed, 1 skipped)
- Temporary probe test of `apply_edit` and `recheck` (path forms, odd stored shapes, skills after a fact is gone, removing entries): run, then removed
- `/check`: not required

## Evidence

- Engine edit rules, ownership filters, hidden-type handling, lock plus advisory lock, `not_latest`, version number, pruning and the `edit:` key read in full and found sound; `_block` keeps `edited`, `index`, `question` and the `omitted` count, and finds sources again by fact id.
- Reproduced: a trailing-newline path is applied (F-193); skills stay listed unflagged after their fact is gone (F-192).
- F-188, F-189, F-190 and F-191 are evidenced by reading `kit-step.tsx`; not run in a browser.

## Findings

- F-188 (P2), F-189 (P2), F-190 (P3), F-191 (P3), F-192 (P3), F-193 (P3). No P0 or P1 open. Verdict is passed because no P0 or P1 finding is open; the two P2 web findings should still be repaired.

## Remaining risk

- The screen was not run in a browser; web findings rest on reading the component.
- Not probed against a live database beyond the existing tests: the concurrent race of an edit with a write in two processes.
- The number check's known gaps (F-185, F-186, F-187) were not re-reviewed.
