# Fix: Make the screen flag instead of remove

**Type:** Fix
**Status:** verified
**Branch:** fix/make-the-screen-flag-instead-of-remove
**Fixes:** F-133, F-137, F-138, F-139

## The problem

Three review rounds on the cheap screen (feature 8a) kept finding wrong removals: a quote
that shares a common word, a denial worded after the match or in another bullet, scattered
words, a prefix word. Each repair added word-matching machinery and the last review still
found holes (F-133, F-137, F-139). The user decided on 2026-11-11: **the screen flags, it
does not remove.** Only the code gates remove a job; a model's reading of a free-text
dealbreaker is shown to the user with its quote and the user decides.

F-138 (P2) is a gate bug and stays a gate repair: a location such as "Nairobi or Remote"
offers remote as one of several modes, but the gate reads it as a clear remote role and
removes a job for an on-site-only track.

## The fix

1. **Outcome `flagged`.** A track's screen outcomes become `passed`, `flagged`, `removed`
   and `unscreened`. `removed` is set only by a code gate (`removed_by` is `gate`). A
   `flagged` row has no `removed_by`, `reason_code` `dealbreaker` and a `reason` of the
   form: `Possible match for your dealbreaker "<dealbreaker>". The posting says: "<quote>"`.
   Migration `0010` replaces the check constraint on `outcome`. It does not edit `0009`,
   which may already be applied on a developer's database.
2. **Flag rule.** A hit becomes a flag when it names one of the user's own dealbreakers and
   its quote is a stretch of the title, company, location or description, at least 6
   characters long, ignoring case and spacing. That keeps a shown quote honest: the model
   cannot make up posting text. Nothing else is checked, so a weak or generic quote can
   produce a flag; that costs the user one glance and removes nothing.
3. **Delete the word-matching.** `_shows`, `_alternatives`, `_negated`, `_same_word`,
   `_words`, the function-word list and their tests go. `Verdict` becomes `Flag`.
4. **Gate (F-138).** A location that lists a work mode as one of several (joined by "or",
   "and", "/" or "&") is unclear, so the gate keeps the job. "Remote, EMEA" and "Hybrid"
   keep working.
5. **Contract.** `JobScreenOut.outcome` may be `flagged`; the web type `ScreenOutcome`
   gains `flagged`. Prompt text is unchanged, so `PROMPT_VERSION` stays `screen-3`.

It must not break: gates removing on clear wording, owner scoping, the 12,000-character cut,
`rules_key` staleness, the failed-re-run rule, the foreign-key handling, and the rule that
posting text is never logged. A removal by a gate still never deletes the job.

## Build steps

- [x] 1. Migration `0010_job_screen_flagged.py` (drop and recreate `ck_job_screen_outcome`
  with `flagged`), the model's check, `tests/test_job_screen_table.py` (a `flagged` row is
  valid, an unknown outcome still fails, `removed` still needs `removed_by`),
  `tests/test_db.py` (head `0010`).
  **Done when:** the table and `test_db.py` tests pass on a fresh test database and on one
  upgraded from `0009`.
- [x] 2. `screen.py`: replace the word-matching with the flag rule (`Flag`, `flag()`), and
  `screening.py`: save `flagged` with the new reason. Rewrite `test_job_screen.py` (real
  quote flags; fabricated quote, short quote and a dealbreaker the user did not write do
  not; a hit in the title flags; a flag never removes) and update `test_job_screening.py`,
  `test_job_screen_routes.py` where they expect a screen removal.
  **Done when:** `pytest tests/test_job_screen.py tests/test_job_screening.py
  tests/test_job_screen_routes.py` passes and no test asserts `removed_by == "screen"`.
- [x] 3. `gates.py` (F-138) with tests in `test_job_gates.py` ("Nairobi or Remote", "Remote /
  Hybrid", "Onsite & remote" keep the job; "Remote, EMEA" and "On-site" still remove).
  **Done when:** `pytest tests/test_job_gates.py` passes, including the 200,000-character
  timing test.
- [x] 4. Web: `ScreenOutcome` gains `flagged` in `web/src/lib/jobs-api.ts` and `removedBy`
  stays `'gate' | null`; its doc comment says a flagged result is a possible match, not a
  removal.
  **Done when:** web lint, typecheck and tests pass.

## Verify

The `Verify` command from `AGENTS.md` must pass, then an independent review (a migration and
untrusted text going to a model). No screen is involved, so no browser check. After the
review, F-133, F-137, F-138 and F-139 are closed by it or reopened with evidence.

## Notes

- This changes behavior of the merged feature 8a on purpose: the spec text of 8a said a
  hit "removes" a job; as of this fix it flags. The 8a archive stays as history.
- Baseline on `main` at `6333814` (this session): web 203 passed and 1 skipped; engine 548
  passed and 9 skipped; lint, typecheck and build pass.

## Step notes

**Built (2026-11-11):** migration `0010_job_screen_flagged.py`; `JobScreen` check; `screen.py` (`Flag`, `flag()`; the word-matching is deleted); `screening.py` (saves `flagged`); `gates.py` (a location that offers choices is unclear); web `ScreenOutcome`; tests rewritten and added. Prompt version stays `screen-3`.

**Verify (this session):** web lint, typecheck and build pass, web tests 203 passed and 1 skipped; engine ruff, format check and mypy pass, engine tests 545 passed and 9 skipped (fewer than 548: the tests of the deleted word-matching are gone). No live model call and no browser check (no screen).



<!-- blueprint:completion {"schemaVersion":2,"specBytes":5456,"specSha256":"229f665c2f85763ca31db471327c7b115fc7e6124a574541599dbca64b3115d3","branch":"refs/heads/fix/make-the-screen-flag-instead-of-remove","head":"fbbb7d076d2ccb3d997c4276e32f0de844ea5337","baseRef":"refs/heads/main","baseCommit":"6333814d3bbaa2edf9ac354ac6162c246dd687b1","sourceTree":"b22a3ba44911fbe56efb468d3c86b572ae23207d","landing":"local-merge","absentOptional":[]} -->

## Findings

### make-the-screen-flag-instead-of-remove/F-133 [P2] closed - The relatedness check passes on any single shared common word, so posting text can still remove a job

**File:** engine/src/engine/jobs/screen.py:141
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security)
**Why it matters:** `_related` accepts a quote that shares one meaningful word (or a 4+ letter prefix) with the dealbreaker. Probed with `verdict`: dealbreaker "No weekend work" with quote "We work with Python and Go" returns a Verdict; dealbreaker "no crypto or gambling companies" with quote "Join one of the best companies" returns a Verdict; "we never ask for an unpaid trial period" removes for "unpaid trial", because a negated mention counts too. A posting that tells the model to report a hit, or a model that misreads, therefore still removes a job on text that does not state the dealbreaker, which is the outcome F-127 and the spec sentence "text inside a posting cannot remove a job unless it contains one of the user's dealbreakers" rule out. The removal is visible and reversible, and the reason shows the quote.
**Suggested fix:** Require the quote to contain all meaningful words (or the whole dealbreaker phrase, folded) and skip a quote preceded by a negation, as the gates do; add tests with a generic-word dealbreaker and a negated quote. Accept a few more extra looks instead of lost jobs.
**Resolution:** Repaired 2026-11-11 (fix `repair-screen-gates-and-quote-rule`): a hit must now show a whole way of meeting the dealbreaker (alternatives split at or, commas and slashes; every meaningful word of one in the quote) and none of those words may sit in a negated sentence of the posting. Tests: generic word, alternatives, partial phrase, denial wordings, a denial in an earlier sentence, the posting repeating the rule itself.
Reopened and repaired again: Repaired 2026-11-11 (fix `make-the-screen-flag-instead-of-remove`, on the user's decision that the screen flags and never removes): the word-matching that decided removals is deleted. A model hit now becomes a `flagged` result, shown as `Possible match for your dealbreaker ... The posting says: "<quote>"`, and removes nothing. It needs the user's own dealbreaker and a quote that is really in the title, company, location or description, so the model cannot show words that are not there. Weak quotes can flag; that costs the user a glance.
Reopened 2026-11-11 by independent review: the single-common-word hole is gone, but `_shows` still removes on text that is a denial or unrelated, probed with `verdict`: (1) a negator after the match is ignored, so "Weekend work is not required", "Relocation not required" and "Weekend work isn't a problem" remove (screen.py:220 looks only before the word); (2) `_CLAUSE_CHARS = 80` means a negator more than 80 characters earlier in the same sentence is missed ("We never ask staff, whatever their seniority ... across our many offices in the region, to do an unpaid trial period" removes); (3) the prefix rule plus "every word anywhere in the quote" lets "no Java" remove on "JavaScript and React experience", "no crypto" on "We use cryptography for security", and "weekend work" on "We work Monday to Friday and weekends are free". Suggested fix: also treat a negator after the match words in the same sentence/quote as a denial, drop or widen the 80-character window to the whole sentence, and require whole-word equality (or a small suffix list) plus words within a short span.
Closed 2026-11-11 by independent review (fresh subagent): `screen.py` no longer holds any removal logic (`flag()` at screen.py:164 only builds a `Flag`), `screening.py:226-230` always writes `removed_by` None for a screen result, and `ck_job_screen_removed` forbids `flagged` with a `removed_by`; throwaway probe against `flag` confirmed a fabricated or sub-6-character quote and a dealbreaker the user did not write give None. A weak real quote now flags by the user's decision, which removes nothing. The remaining legacy-row and wording issues are F-140 and F-141.

### make-the-screen-flag-instead-of-remove/F-137 [P3] closed - The negation check ignores line breaks, so a denial in one bullet hides a real hit in the next

**File:** engine/src/engine/jobs/screen.py:151
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality)
**Why it matters:** The spec says a negator "earlier in the same sentence or line". `_fold` turns every newline into a space before `_negated` runs, so a bullet list without full stops is one sentence: "Benefits:\n- No degree required\n- Unpaid trial period of two weeks" with dealbreaker "unpaid trial" returns no verdict. The error is in the safe direction (a missed removal), but the stated contract is not met and bulleted postings are common.
**Suggested fix:** Run `_negated` on text that keeps line breaks (or fold newlines to ". " for this check only) and add a bulleted-list test.
**Resolution:** Superseded 2026-11-11 by the same fix: the negation check that ignored line breaks no longer exists, because the screen no longer decides removals.
Closed 2026-11-11 by independent review (fresh subagent): `_negated` and the sentence logic are deleted (git diff 6333814..fbbb7d0 on screen.py); a bullet list can no longer hide or cause a removal because the screen removes nothing.

### make-the-screen-flag-instead-of-remove/F-139 [P3] closed - New tests only cover negators before the match and one sentence, so the remaining holes pass unnoticed

**File:** engine/tests/test_job_screen.py:96, engine/tests/test_job_gates.py:70
**Found:** 2026-11-11 by /audit independent (scope: current; lens: tests)
**Why it matters:** `test_a_denial_in_the_posting_is_not_a_hit` uses only negators before the words in a short sentence; nothing covers a trailing denial ("is not required"), a negator beyond the 80-character window, a bulleted list, a prefix match ("Java" against "JavaScript"), words scattered across a long quote, or "Nairobi or Remote" in the location. Those are the behaviours F-133, F-137 and F-138 record, so the suite proves the repaired wordings but not the rule it claims.
**Suggested fix:** Add one test per wording above once the rule is decided.
**Resolution:** Superseded 2026-11-11 by the same fix: the tests that covered the removed negation and word rules are replaced by tests of the flag rule (own dealbreaker, real quote, minimum length, first valid hit, flag never removes).
Closed 2026-11-11 by independent review (fresh subagent): the negation, prefix and scattered-word behaviours the tests were missing no longer exist; `test_job_screen.py` now tests the flag rule (own dealbreaker, real quote, minimum length, first valid hit). Gaps that remain in the new tests are F-142.

## Independent review

**Status:** passed
**Target commit:** fbbb7d076d2ccb3d997c4276e32f0de844ea5337
**Base commit:** 6333814d3bbaa2edf9ac354ac6162c246dd687b1
**Base ref:** main
**Spec hash:** 229f665c2f85763ca31db471327c7b115fc7e6124a574541599dbca64b3115d3
**Prepared by:** claude
**Builder model:** claude-fable-5-2
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T04:03:41Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T04:09:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `sha256sum blueprint/context/current-feature.md`, `git status --short`: pass (all match the request; only review.md and findings.md changed)
- `git diff 6333814d..fbbb7d07` (complete delta read): pass
- `cd engine && uv run --env-file ../.env pytest -q`: pass (545 passed, 9 skipped)
- `cd engine && uv run ruff check .`: pass
- `cd engine && uv run mypy`: pass (95 source files)
- `cd web && npm run lint && npm run typecheck && npm test`: pass (203 passed, 1 skipped)
- Throwaway probes in /tmp/rv2 (`run_gates` wordings and 200,000-character timing, `flag` quote cases): ran, results in Evidence
- `/check`: not-required

## Evidence

- `run_gates` on an on-site-only track: "Nairobi or Remote", "Remote / Hybrid", "remote OR on-site" are kept; "Nairobi (Remote work not allowed)" still returns `work_mode` (F-138 reopened).
- `_OFFERS` timing: 200,000 to 250,000-character locations and descriptions ("Remote or " repeated, "remote / " repeated, long spaces) ran in under 0.06 s; the regex is linear, no backtracking found.
- `flag`: fabricated quote, 5-character quote and a dealbreaker the user did not write give None; a real quote, case/space-folded, flags with the user's own spelling; "Acme. Eng" (spans two fields) and "......" also flag (F-141).
- Migration 0010: constraint name `ck_job_screen_outcome` matches the model; `ck_job_screen_removed` allows `flagged` with null `removed_by`; upgrade keeps rows and the table test passes from 0009; legacy `removed`/`screen` rows are left as removals and `ck_job_screen_removed_by` still allows `screen` (F-140); downgrade leaves the flag reason on `passed` rows (F-143).
- Owner scoping (`_owned_job`, `_tracks`, `list_screens` filter on user id), the upsert failed-re-run rule and the no-logging of posting text are unchanged by the delta and their tests pass.
- Dead code: no remaining reference to `_shows`, `_negated`, `_same_word`, `Verdict` in engine, web or docs outside archived history; one stale comment at screening.py:213 (F-142).
- Closed with evidence: F-133, F-137, F-139. Reopened: F-138.

## Findings

- F-138 [P2] reopened: a location "Nairobi (Remote work not allowed)" still removes an on-site-only track (gates.py:68/83)
- F-140 [P2] open: legacy `removed`/`screen` rows survive migration 0010 and `screen` remains an allowed remover in the check, model and web type
- F-141 [P3] open: a flag quote can span two fields or be only punctuation
- F-142 [P3] open: stale comment and weak or missing tests (hasattr assertion, no route-level flagged test, no flagged-then-failed-rerun test)
- F-143 [P3] open: downgrade leaves the flag reason on `passed` rows

## Remaining risk

- No P0 or P1 finding is open or fixed, so the receipt passes. Open P2 findings F-138 and F-140 should still be repaired before the feature closes: F-138 means a job whose location says remote work is not allowed can still be removed by the gate for an on-site-only track; F-140 means rows removed by the old screen on an existing database stay removed.
- The flag rule accepts any real quote of 6 or more characters (by the user's decision), so a hostile posting can make the app flag an unrelated stretch of its own text against one of the user's real dealbreakers; it removes nothing.
- No live model call, no browser check and no real-database upgrade of existing production rows was run; the migration was checked by code reading and the 0009 to 0010 table test.
