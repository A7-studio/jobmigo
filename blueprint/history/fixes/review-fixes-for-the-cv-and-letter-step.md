# Fix: Review fixes for the CV and letter step

**Type:** Fix
**Status:** verified
**Branch:** fix/11b-review-findings
**Fixes:** F-188, F-189, F-190, F-191, F-192, F-193

## The problem

The independent review of 11b (9e21309) passed but left six findings. The serious one, F-188: with
the edit box open on one statement, removing another changed the paths, and Save then overwrote the
statement that had moved into the old path with the old text. F-189 threw the typed text away before
the save had worked. F-190 to F-193 are smaller: the question box could not be cleared, every Edit
and Remove button had the same name and focus was lost, the recheck ignored CV skills, and the path
pattern accepted a trailing newline.

## The fix

1. **F-188.** The document component is keyed by the version, so a new version starts with nothing
   open and no path can point at a moved statement. While one statement is open, Edit and Remove on
   every other statement (and Remove on skills) are disabled.
2. **F-189.** The editor stays open, with the typed text, until the save has worked (the new version
   then replaces the document). A failed save shows its calm message beside the editor, "Your text is
   still here". The box has the engine's limit as `maxLength` and shows "n of N characters".
3. **F-190.** The question box is `null` until touched, so clearing it stays cleared.
4. **F-191.** Each Edit and Remove button names its statement ("Edit Lead at BeatBnk: Cut bugs by...").
   Opening the editor focuses the box; Cancel returns focus to that statement's Edit button; a saved
   or removed statement is announced ("Saved as a new version.") and focus moves to that message.
5. **F-192.** The recheck drops a CV skill whose fact is gone and counts it in `omitted`. A skill can
   now be removed (`skills.N`, remove only) and the screen shows a Remove button per skill.
6. **F-193.** Paths are matched with `fullmatch` and ASCII digits only.

## Build steps

- [x] 1. Engine: path rule and skills (`kit_edit.py`), tests written first and seen to fail.
- [x] 2. Web: `kit-step.tsx`, `kit-view.ts` (`blockLimit`, `preview`) and tests.
- [x] 3. Verify; browser check; independent review; archive; merge.

## Verify

Engine and web suites, lint, typecheck and build. The web has no rendering test setup (adding one
means new dependencies), so the screen fixes (F-188 to F-191) are checked in a browser.

## Notes

- Verify: engine 874 passed, 11 skipped; ruff, format and mypy pass. Web lint, typecheck and build
  pass; web tests 250 passed, 1 skipped. Not yet seen in a browser.

- Only the screen file changed behaviour for F-188 to F-191; no engine contract changed except the
  new removable `skills.N` path and the stricter path match.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":2745,"specSha256":"b612781ce9a987b72217974ebac2c4bfdc4cbfc7cc5da7fdcca5cc8c9d7a3412","branch":"refs/heads/fix/11b-review-findings","head":"e300c028ff7da990d1d770253fb337d35da14c9d","baseRef":"refs/heads/main","baseCommit":"1fcf443f057d51858507811387254e59409c6f19","sourceTree":"cf96ebc0a0a5254b8ac6eff39116b3fcca267b5a","landing":"local-merge","absentOptional":[]} -->

## Findings

### review-fixes-for-the-cv-and-letter-step/F-175 [P3] closed - After adding a track in Profile, the Fit step can still show "Add a ... track" for up to 30 seconds

**File:** web/src/components/jobs/fit-step.tsx:60
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** The Fit step reads tracks under the key `['fit-tracks']` while the Profile page creates and invalidates `['tracks']` (profile.tsx:165, :173). The query client has `staleTime: 30_000` (router.tsx:7), so returning to the job within 30 seconds of adding the matching-type track serves the cached list and repeats the empty state that sent the person to Profile. The new empty state makes this the main path for gig and AI training jobs. Evidenced by reading the keys and config; not run in a browser.
**Suggested fix:** Use the same `['tracks']` key in the Fit step, or invalidate `['fit-tracks']` where tracks change.
**Resolution:** Not reproduced in a browser on 2026-11-11: after adding a matching track in Profile and returning to the job through the app's links, the Fit step listed the new track. The cache window may have passed; the code reading still stands.
Closed 2026-11-11 by feature 11b: the Fit step and the CV and letter step now read tracks under `['tracks']`, the key Profile invalidates; the independent review of 11b (9e21309) confirmed both use the same query and data.

### review-fixes-for-the-cv-and-letter-step/F-188 [P2] closed - An open edit box survives a Remove of another statement; the paths shift and Save overwrites a different statement

**File:** web/src/components/jobs/kit-step.tsx:333
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** `Document` keeps `editing = {path, text}` in its own state and never clears it when the version changes (`change.onSuccess` only resets `picked`; `Document` has no `key`). While one statement is open for editing, the Edit and Remove buttons of every other statement stay visible. Edit `entries.1.bullets.3`, then Remove `entries.1.bullets.1` on the same page: the engine saves a new version in which the old bullet 4 is now `entries.1.bullets.3`, the open textarea still holds the old bullet 3's text, and Save sends `edit` for `entries.1.bullets.3`, so the person's text silently replaces a different statement (the former bullet 4). The same stale path applies after any version change (a write again, a reload after 409). Evidenced by reading the component state flow; not run in a browser.
**Suggested fix:** Clear `editing` whenever `version.id` changes (give `Document` `key={shown.id}`), or hide Edit and Remove on all other statements while one is being edited; send the version's own statement text check (or the old text) with the path if a stronger guard is wanted.
**Resolution:** Repaired 2026-11-11: the document is keyed by the version, so a new version starts with no statement open; Edit and Remove on every other statement are disabled while one is open.
Closed 2026-11-11 by independent review (fresh subagent, e300c02): every mutation takes the version and path from one render, the document is keyed by the version, other statements are disabled while one is open, and the engine refuses any version but the latest (409).

### review-fixes-for-the-cv-and-letter-step/F-189 [P2] closed - The typed edit is thrown away before the save succeeds, so a refused or failed save loses the person's text

**File:** web/src/components/jobs/kit-step.tsx:324
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** `onSave` calls `onChange(...)` (which starts the mutation) and immediately `setEditing(null)`. If the engine answers `invalid_edit` (for example text over the block's cap: the textarea has no `maxLength` or counter, and the summary, bullet, paragraph and answer caps differ), `not_latest`, or the network fails, the page shows "Check the text and try again" while the text the person wrote is gone and the statement shows the old wording. Long cover letter paragraphs make an over-cap save plausible.
**Suggested fix:** Close the editor in the mutation's `onSuccess` and keep the text on error; show the cap in the textarea (`maxLength` or a counter) using the engine limits.
**Resolution:** Repaired 2026-11-11: the editor closes only when the save has worked; a failed save keeps the typed text and shows its message beside the editor; the box has `maxLength` and a character count from the engine's limits (`blockLimit`).
Closed 2026-11-11 by independent review (fresh subagent, e300c02): the editor stays open with the typed text until the new version arrives; a failed save shows its message beside the editor and cannot show on another statement.

### review-fixes-for-the-cv-and-letter-step/F-190 [P3] closed - Once an answers document exists, the question box cannot be emptied, so "write again" always re-sends the old questions

**File:** web/src/components/jobs/kit-step.tsx:158
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** `questionsValue` falls back to the saved answers' questions whenever the local `questions` state is `''`. A person who deletes all text to write the kit again without questions sees the old questions reappear, and `startWriting` sends them, so an answers document is written (and paid for) again. Evidenced by reading; not run in a browser.
**Suggested fix:** Track "touched" separately from the value (null until the person types), so an empty string is a real choice.
**Resolution:** Repaired 2026-11-11: the question box is `null` until touched, so an emptied box stays empty.
Closed 2026-11-11 by independent review (fresh subagent, e300c02): the question box is null until touched.

### review-fixes-for-the-cv-and-letter-step/F-191 [P3] closed - Edit and Remove buttons share one name for every statement, and focus is lost after Save, Cancel and Remove

**File:** web/src/components/jobs/kit-step.tsx:392
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness, accessibility)
**Why it matters:** A screen reader lists many buttons named only "Edit" and "Remove" with no statement named; Remove has no confirmation and no live announcement of the result. Pressing Edit does not move focus into the textarea, and when Save, Cancel or Remove unmounts the focused button, focus drops to the page body. Saving also has no `role="status"` message.
**Suggested fix:** Give each button an `aria-label` that names the statement (for example "Edit statement in Summary"), focus the textarea on Edit and the statement or its Edit button after Save or Cancel, and announce a save or removal in a status region.
**Resolution:** Repaired 2026-11-11: Edit and Remove buttons name their statement; focus goes into the box on Edit and back to the Edit button on Cancel; saving or removing is announced and focus moves to the message.
Closed 2026-11-11 by independent review (fresh subagent, e300c02): buttons name their statements and focus follows the action; the one gap, a repeated notice, is recorded as F-195.

### review-fixes-for-the-cv-and-letter-step/F-192 [P3] closed - The recheck never looks at a CV's skills (or entry headings), so a skill whose fact is gone or edited stays listed unflagged

**File:** engine/src/engine/jobs/kit_edit.py:123
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** The spec says the whole document is checked again from the facts of the version's own profile that are still confirmed or edited. `recheck` copies `skills` through untouched: with the skill fact removed from the facts, the saved version still lists `{"name": "Flutter"}` and reports `flagged: 0` (reproduced with `recheck` on the test CV). The skills line shows the old fact wording, and `omitted` is not raised. The skills are not editable or removable either, so a person cannot fix the line. Entries whose own fact is gone keep their heading but their bullets are flagged `off_entry`, which hides the cause.
**Suggested fix:** Drop skills (and count them in `omitted`) whose fact id is no longer among the facts, or flag them; refresh the name from the fact's current text.
**Resolution:** Repaired 2026-11-11: the recheck drops a CV skill whose fact is gone and counts it in `omitted`; a skill can be removed (`skills.N`) from the screen. Tests: gone skill, removable and not editable.
Closed 2026-11-11 by independent review (fresh subagent, e300c02): the recheck drops a skill whose id is missing or whose fact is gone and counts it once; `skills.N` is remove-only.

### review-fixes-for-the-cv-and-letter-step/F-193 [P3] closed - The path pattern ends in `$`, which accepts a trailing newline: `entries.1.bullets.1\n` is applied

**File:** engine/src/engine/jobs/kit_edit.py:28
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security)
**Why it matters:** `re.match` with `$` matches before a final newline, and `int("1\n")` succeeds, so a path with a trailing newline is accepted as the statement `entries.1.bullets.1` (reproduced with `apply_edit`; `paragraphs.1\n` and `summary\n` fail later only by luck of the checks). The raw path also goes into the cache-key material, so equal edits with different paths get different keys. No data exposure; it is a validation looseness in a function whose job is a strict path grammar.
**Suggested fix:** Use `re.fullmatch` with `[0-9]` instead of `\d` (which also reads other Unicode digits), and add a test for a trailing newline.
**Resolution:** Repaired 2026-11-11: paths are matched with `fullmatch` and ASCII digits only. Tests: trailing newline, leading space, Arabic-Indic and full-width digits are refused.
Closed 2026-11-11 by independent review (fresh subagent, e300c02): a trailing newline, a leading space and non-ASCII digits are refused.

## Independent review

**Status:** passed
**Target commit:** e300c028ff7da990d1d770253fb337d35da14c9d
**Base commit:** 1fcf443f057d51858507811387254e59409c6f19
**Base ref:** main
**Spec hash:** b612781ce9a987b72217974ebac2c4bfdc4cbfc7cc5da7fdcca5cc8c9d7a3412
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T19:32:05Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T19:55:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Handoff

Review the active spec and the complete `main..target` delta in a fresh
session or isolated subagent without the builder conversation. Run all Audit lenses from scratch.
Do not edit product code, accept findings, or reuse the existing findings as the review scope.

## Commands

- `uv run --env-file ../.env pytest -q tests/test_kit_edit.py tests/test_kitting.py tests/test_kit_routes.py` (engine): pass, 85 passed
- `npm test` (web): pass
- `npm run lint` (web): pass
- `npx tsc --noEmit` (web): pass
- Temporary probe test (astral and whitespace edits, malformed skills): run and removed

## Evidence

- F-188: every `change.mutate` takes `kitId` and path from one render of the version shown, `Document` is keyed by `shown.id`, other statements are disabled while one is open, and the engine answers 409 `not_latest` for any other version, so two quick clicks or a double submit cannot reach another statement.
- F-189: the editor stays open until the refetch brings the new version; typed text and the in-editor alert survive a failed save; `onStartEdit` resets the error.
- F-192: `recheck` drops a skill whose id is missing or not among the facts and counts it once; a repeated recheck does not recount (omitted is carried forward); a removed skill is not counted; `skills.N` is remove-only.
- F-193: `fullmatch` with `[0-9]`; probes with newline, space, Arabic-Indic and full-width digits are refused.
- Reproduced: the engine accepts 300 code points (450 UTF-16 units) and a 420-character raw text that cleans to 239, which the web `maxLength` of 300 would cut (F-194).

## Findings

- F-194 (P3), F-195 (P3), F-196 (P3), all open. No P0 or P1.

## Remaining risk

- No DOM test setup: the focus, notice, status-region and disabled-button behaviour were reasoned from the code, not run in a browser.
- Whether a browser drops focus when the Save button becomes disabled during a save was not verified.
- `recheck` still crashes (500) on stored content whose `skills` is null, not a list of objects, or has an unhashable id; the same holds for entries. Content is written only by the engine, so this was not raised as a finding.
- Engine limits are duplicated by hand in `blockLimit` with no cross-check test.
