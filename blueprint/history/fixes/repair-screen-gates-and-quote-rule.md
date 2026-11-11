# Fix: Repair screen gates and quote rule

**Type:** Fix
**Status:** verified
**Branch:** fix/repair-screen-gates-and-quote-rule
**Fixes:** F-130, F-133, F-134, F-135, F-136

## The problem

The second independent review of feature 8a passed it but left findings in the screen that
can still remove a job wrongly or hide a defect. All were reproduced by the reviewer with
probes. A wrongly removed job is worse than an extra look, so these are repaired before the
screen is put in front of the user (feature 8c).

- **F-134 (P2)** `engine/src/engine/jobs/gates.py`: the location field is matched with a
  bare `remote` or `hybrid` or `on-site` word, so "Nairobi (not remote)" removes an
  on-site-only track. "Fully remote is not an option here" and "Remote only during
  onboarding, then on-site role" also count as a clear work mode. "Candidates outside the
  US only" removes a job for a Kenya-eligible track.
- **F-133 (P2)** `engine/src/engine/jobs/screen.py`: `_related` accepts one shared common
  word, so "We work with Python and Go" removes a job for the dealbreaker "No weekend
  work", and a negated mention ("we never ask for an unpaid trial period") counts as a hit.
- **F-135 (P3)** `screen.py`, `screening.py`: the quote is checked only against the
  description, although the title, company and location are in the prompt, outside the
  data delimiters, and the gates read them. A dealbreaker that appears only in the title
  can never remove a job.
- **F-130 (P3, reopened)** `screening.py`: the savepoint repair swallows every
  `IntegrityError` while the job exists, so a check-constraint bug would silently drop a
  row and still answer 200.
- **F-136 (P3)** `engine/tests/test_job_screening.py`: untested: the `ai_invalid`
  classification, the 12,000-character cut, the `rules_key` inputs beyond three edits, and
  a job deleted mid-run.

## The fix

Root-cause repairs inside the files above. No new dependency, table or setting.

1. **Gates (F-134).** Apply the negation check to the location field as well as to the
   description. A work-mode or region phrase followed by a negation or a limit ("is not",
   "not available", "during", "until", "initially", "temporarily") is unclear and does not
   count. A region phrase preceded by "outside", "excluding", "except", "other than" or
   "non" is unclear and does not count. Existing clear cases ("fully remote role", "US
   only", "on-site role") must keep removing.
2. **Quote rule (F-133).** A hit must show the whole dealbreaker, not one word. Split the
   dealbreaker into alternatives at "or", commas and slashes; every meaningful word of one
   alternative must appear in the quote (same word-form rule as now), so "no crypto or
   gambling companies" can remove on "gambling companies" but not on "companies" alone. A
   hit is also ignored when the matched wording sits in a negated clause of the posting
   (a negator such as not, no, never, without, n't, neither or nor earlier in the same
   sentence or line). A posting that says "No weekend work" therefore does not trigger the
   dealbreaker "No weekend work": that is the opposite of the rule.
3. **Fields (F-135).** Put the title, company and location inside the delimited `<posting>`
   block, and check the quote against title, company, location and description together.
   The prompt text changes, so `PROMPT_VERSION` becomes `screen-3`.
4. **Save (F-130).** Treat only a foreign-key violation (SQLSTATE `23503`) as a deleted job
   or track, as now; let every other integrity error propagate as the 500 it is.
5. **Tests (F-136).** One test per item in F-136, and a test per repaired wording above.

It must not break: the clear removals the first review required, the rule that a hit needs
one of the user's own dealbreakers and a real quote, owner scoping, and the conservative
direction (a doubt keeps the job in).

## Build steps

- [x] 1. Gates: repair F-134 in `gates.py`; extend `engine/tests/test_job_gates.py` with a
  case for each wording above and for the clear cases that must still remove.
  **Done when:** `uv run --env-file ../.env pytest tests/test_job_gates.py` passes, and a
  200,000-character posting of repeated "not remote" and "outside the US only" runs every
  gate in under 1 second.
- [x] 2. Screen task: repair F-133 and F-135 in `screen.py` and `screening.py` (title,
  company and location in the delimited block, quote checked against all four fields),
  bump the prompt to `screen-3`; update and extend `test_job_screen.py`.
  **Done when:** `pytest tests/test_job_screen.py tests/test_job_screening.py` passes, with
  the generic-word, alternative, negated-clause and title-only cases shown.
- [x] 3. Service: repair F-130 (only a foreign-key violation is swallowed) and add the F-136
  tests to `test_job_screening.py`.
  **Done when:** `pytest tests/test_job_screening.py` passes, including a non-foreign-key
  integrity error that propagates, `ai_invalid` through `screen_job`, a description over
  12,000 characters, `rules_key` changing for target roles, locations, eligibility and a
  must-have label, and a job deleted mid-run answering `not_found`.

## Verify

The `Verify` command from `AGENTS.md` must pass. Then `/audit current` re-reviews the repaired
files and moves the findings to `closed`. No screen is involved, so no browser check.

## Notes

- The independent-review gate applies (a security boundary and untrusted text going to a
  model): this fix needs a fresh reviewer before it lands, as 8a did.
- Baseline on `main` at `beb0de0` (this session): web 203 passed and 1 skipped; engine 527
  passed and 9 skipped; lint, typecheck and build pass.

## Step notes

**Built (2026-11-11):** `gates.py` (negation on the location field, taken-back and limited phrases, regions turned inside out); `screen.py` (`_shows` replaces `_related`: whole alternative of the dealbreaker, negated sentences ignored; title, company and location inside the data block; prompt `screen-3`); `screening.py` (quote checked against all four fields; only a foreign-key violation is swallowed); new tests in `test_job_gates.py`, `test_job_screen.py` and `test_job_screening.py`.

**Verify (this session):** web lint, typecheck and build pass, web tests 203 passed and 1 skipped; engine ruff, format check and mypy pass, engine tests 548 passed and 9 skipped. No live model call and no browser check (no screen).



<!-- blueprint:completion {"schemaVersion":2,"specBytes":6388,"specSha256":"64e1f45772865fadeac02b710b5474391958f86b601686988bf45c8016dac0fb","branch":"refs/heads/fix/repair-screen-gates-and-quote-rule","head":"d7535e370b61807564a3b48c0d2b3576ba4e308a","baseRef":"refs/heads/main","baseCommit":"beb0de09a39432d602ba46434b83fd277a6bfacf","sourceTree":"f99a3e883cd5228a3409c55f85395aa2d9fca045","landing":"local-merge","absentOptional":[]} -->

## Findings

### repair-screen-gates-and-quote-rule/F-130 [P3] closed - Any IntegrityError while saving is reported as `not_found`, and one deleted track fails the whole batch

**File:** engine/src/engine/jobs/screening.py:258
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality)
**Why it matters:** The comment assumes a foreign key failure, but a check-constraint violation (a future bug writing an invalid outcome or `removed_by`) is also an `IntegrityError` and would be shown to the user as "not found", hiding the defect. A track deleted mid-run also discards the results of every other track and returns 404 for a job that still exists. Also, the gather of model calls has no `return_exceptions`, so an unexpected error in one track leaves the other calls running (and billed) with their results dropped.
**Suggested fix:** Check `error.orig` for a foreign key violation, skip rows whose track is gone, and let other errors propagate as 500.
**Resolution:** Repaired 2026-11-11: each row is saved in a savepoint; an integrity error is `not_found` only when the job is gone, a deleted track just has no row, and the model calls are gathered with `return_exceptions` so every call finishes, the successful results are saved, and then the first failure is raised. Tests cover a track deleted mid-run and an unexpected failure that still saves the other result.
Reopened 2026-11-11 by independent review: the repair introduced a new problem. `except IntegrityError` at `screening.py:283` now swallows every integrity error while the job still exists, not only a missing track, so a check-constraint violation (a future bug writing an invalid outcome or `removed_by`) silently drops that track's row and the call still returns 200. The original suggestion was to inspect `error.orig` for a foreign key violation and let other errors propagate. No test covers it.
Repaired again 2026-11-11 (fix `repair-screen-gates-and-quote-rule`): only a foreign-key violation (SQLSTATE 23503) is treated as a deleted job or track; any other integrity error propagates. Tests: a check-constraint error propagates and saves nothing, a job deleted mid-run is `not_found`, a deleted track is skipped.
Closed 2026-11-11 by independent review of fix `repair-screen-gates-and-quote-rule`: `_is_foreign_key` reads `error.orig.sqlstate`, which SQLAlchemy's asyncpg adapter sets from the driver error (sqlalchemy/dialects/postgresql/asyncpg.py:987). The deleted-job and deleted-track tests pass (proving 23503 is read in this stack) and the `bogus` outcome test proves a check-constraint IntegrityError propagates with nothing saved. Engine suite 548 passed.

### repair-screen-gates-and-quote-rule/F-134 [P2] closed - Gates still remove on a location field that says "not remote" and on "outside the US only"

**File:** engine/src/engine/jobs/gates.py:96, engine/src/engine/jobs/gates.py:139
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality)
**Why it matters:** Throwaway probes: location "Nairobi (not remote)" on an on-site-only track returns `work_mode` (the location field is matched with a bare `\bremote\b` and no negation check); "Fully remote is not an option here" and "Remote only during onboarding, then on-site role" also remove; "Candidates outside the US only" with eligibility "Kenya" returns `region_only` although it welcomes exactly the people the track describes. A wrongly removed job is the outcome the spec says is worse than an extra model call.
**Suggested fix:** Apply the negation check to the location field, treat "outside"/"excluding"/"non" before a region as unclear, and skip a phrase followed by "is not"/"not available"; add a test for each.
**Resolution:** Repaired 2026-11-11: the location field gets the same negation check; a phrase followed by a denial or limit ("is not", "during", "until") and a region preceded by outside, excluding, except, other than or non no longer count. Tests for each reviewed wording, the clear removals that must remain, and a 200,000-character timing case.
Closed 2026-11-11 by independent review of fix `repair-screen-gates-and-quote-rule`: probes confirm "Nairobi, Kenya (not remote)", "This is not a fully remote role", "Candidates in Kenya or non-US welcome" and the test wordings are kept; clear cases ("Remote" location, "US only", "fully remote role") still remove; a 200,000-character mix of the hostile wordings ran six gate passes in 0.09 s (the lookbehind is a 24-character slice, no backtracking). A different wording the repair does not cover is filed as F-138.

### repair-screen-gates-and-quote-rule/F-135 [P3] closed - The screen's quote check ignores the title, company and location, though the gates and the model read them

**File:** engine/src/engine/jobs/screening.py:213
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality)
**Why it matters:** `verdict` checks quotes against `job.description` only, but the prompt also gives the model the title, company and location (outside the `<posting>` delimiters, so they are not marked as data) and the gates read the title and location. A dealbreaker that is stated only in the title or location (for example "Crypto Exchange Engineer") can never remove a job through the screen, because the model's quote is not found in the description, and the job passes silently. Those three fields are untrusted posting text that sits in the prompt as plain lines.
**Suggested fix:** Check quotes against title, location and description together, and put the three fields inside the delimited data block; add a test for a title-only dealbreaker.
**Resolution:** Repaired 2026-11-11: title, company and location are now inside the delimited posting block (prompt `screen-3`) and the quote is checked against title, company, location and description together, joined with full stops. Tests: a title-only dealbreaker removes, and a closing tag in the title cannot end the block.
Closed 2026-11-11 by independent review: `screening.py:214` joins title, company, location and description with full stops and `verdict` checks quotes against it; `_user_message` puts all three fields inside `<posting>` and `_safe` neutralises `</posting`; field lengths are already capped at 120/200 on the write path. Title-only and closing-tag tests pass.

### repair-screen-gates-and-quote-rule/F-136 [P3] closed - Tests do not cover the invalid-reply classification, the 12,000-character cut, or the rules_key inputs beyond three edits

**File:** engine/tests/test_job_screening.py:155
**Found:** 2026-11-11 by /audit independent (scope: current; lens: tests)
**Why it matters:** `ai_invalid` (an `AiOutputInvalidError` through `screen_job`) is never run, so the mapping in `UNSCREENED` for that code is unproven; no test saves a job with a description over `MAX_POSTING_CHARS` (the clip in `_screen_input` is what keeps `ScreenInput` valid); the stale test edits only dealbreakers, work modes and do-not-apply, not target roles, locations, eligibility or criteria labels that `rules_key` also hashes; a job deleted mid-run (the `not_found` branch) is untested.
**Suggested fix:** Add one test per item above against the test database.
**Resolution:** Repaired 2026-11-11: tests added for `ai_invalid`, a posting over 12,000 characters (cut for the model, checked whole), `rules_key` for target roles, locations, eligibility and a must-have label, and a job deleted mid-run.
Closed 2026-11-11 by independent review: the added tests exist and pass against the test database (ai_invalid, over-12,000-character cut, rules_key for four more inputs, job deleted mid-run); weaknesses in the new tests are filed as F-139.

## Independent review

**Status:** passed
**Target commit:** d7535e370b61807564a3b48c0d2b3576ba4e308a
**Base commit:** beb0de09a39432d602ba46434b83fd277a6bfacf
**Base ref:** main
**Spec hash:** 64e1f45772865fadeac02b710b5474391958f86b601686988bf45c8016dac0fb
**Prepared by:** claude
**Builder model:** claude-fable-5-2
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T03:30:36Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T03:35:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Handoff

Review the active spec and the complete `<base>..<target>` delta in a fresh
session or isolated subagent without the builder conversation. Run all Audit lenses from scratch.
Run Check when required above. Do not edit product code, accept findings, or
reuse the existing findings as the review scope.

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `sha256sum blueprint/context/current-feature.md`, `git status --short`: pass (all match the request; only review.md and findings.md differ)
- `cd engine && uv run --env-file ../.env pytest -q`: pass (548 passed, 9 skipped)
- `cd engine && uv run ruff check .`: pass
- `cd engine && uv run mypy`: pass (95 source files)
- Throwaway probes under /tmp/rv (verdict and run_gates on crafted wordings, 200,000-character gate timing): ran, results in Evidence
- web lint, typecheck and tests: not run (the delta touches no web file)

## Evidence

- Reviewed the whole `beb0de0..d7535e3` delta (gates.py, screen.py, screening.py and the three test files) plus the full current source of the three modules.
- Gates: "Nairobi, Kenya (not remote)", "This is not a fully remote role" and non-US wordings stay in; clear cases still remove; six gate passes over 200,000-character hostile postings took 0.09 s (24-character lookbehind, no backtracking).
- Screen: probes show trailing negations, a negator beyond 80 characters, prefix matches ("Java" and "JavaScript") and scattered words still remove (F-133 reopened); newline folding defeats the "line" rule (F-137).
- `_is_foreign_key` reads `error.orig.sqlstate`, set by SQLAlchemy's asyncpg adapter (sqlalchemy/dialects/postgresql/asyncpg.py:987); the deleted-job and deleted-track tests pass, and the `bogus` outcome test proves a check-constraint IntegrityError propagates with nothing saved (F-130 closed).
- Title, company and location sit inside `<posting>` with `</posting` neutralised and their lengths capped at 120/200 on the write path (F-135 closed).
- F-134 and F-136 closed on the probes and passing tests above.

## Findings

- New: F-137 [P3], F-138 [P2], F-139 [P3] (all open)
- Reopened: F-133 [P2] (open)
- Closed: F-130, F-134, F-135, F-136
- No P0 or P1 finding is open or fixed

## Remaining risk

- The screen can still remove a job wrongly on a denial worded after the match, a very long sentence, a prefix word or scattered words (F-133), and the gate can remove an on-site-only track on a location such as "Nairobi or Remote" (F-138); both are P2 and non-blocking, to be repaired before the screen reaches the user in feature 8c.
- No live model call, no browser check and no web checks were run; model replies were exercised only through fakes.
