# Fix: Clean up open review findings

**Type:** Fix
**Status:** verified
**Branch:** fix/clean-up-open-review-findings
**Fixes:** F-138, F-140, F-141, F-142, F-143, F-148, F-149, F-150, F-151, F-152, F-153

## The problem

The independent reviews of features 8a and 8b passed both but left eleven open findings,
four of them P2. The user chose to clear them before the Fit step (8c) puts the screen and
the evaluation in front of them. All were reproduced by a reviewer with probes.

- **F-138 (P2)** gates: a location such as "Nairobi (Remote work not allowed)" still reads
  as a clear remote role and removes a job for an on-site-only track.
- **F-140 (P2)** and **F-143 (P3)** migration `0010`: rows the old screen wrote as `removed`
  by `screen` stay removals, the check still allows `screen` as a remover, the web type
  still says `'gate' | 'screen' | null`, and the downgrade leaves a flag's reason on a
  `passed` row.
- **F-148 (P2)**, **F-149 (P2)**, **F-152 (P3)** `eval_extract.py`: negated importance
  wording ("Not required", "must not") states a must-have; headings the word lists do not
  know, or an unrelated section such as "Responsibilities", leave the wrong importance
  standing; a quote can span two fields, start mid-word, or repeat elsewhere.
- **F-141 (P3)** and **F-142 (P3)** screen: a flag can show a quote that spans two fields
  or is only punctuation; a stale comment, a test that proves nothing, no route test for a
  flagged result and none for a failed re-run over a flag.
- **F-150 (P3)** pay: a shared-suffix range ("3-4k", "80-100k") drops the pay or accepts a
  bare "3"; "3.000" and "3 000" are dropped.
- **F-151 (P3)** a reply with more than 60 requirements or judgements is refused, not cut.
- **F-153 (P3)** evaluation selects and upsert do not filter on `user_id`.

## The fix

Root-cause repairs inside the files these findings name. No new dependency or setting.

1. **Gates (F-138).** In the location field, a mode word that sits in a list or alternative,
   or in a location that also holds a denial word (not, no, never, without, n't), makes the
   whole posting's mode unclear. Clear cases ("Remote, EMEA", "On-site", "Hybrid") keep
   working.
2. **Migration `0012_job_screen_gate_only.py` (F-140).** Rows with `removed_by = 'screen'`
   become `flagged` (outcome), `removed_by` null, reason `Possible match for your
   dealbreaker ...` (the old `You ruled out ` prefix replaced); the check on `removed_by`
   narrows to `'gate'`; the downgrade restores the wider check. The model, `JobScreenOut`
   (`Literal["gate"] | None`) and the web type (`'gate' | null`) follow. `0010`'s downgrade
   also clears `reason_code` and `reason` on the rows it turns into `passed` (F-143).
3. **Quotes (F-141, F-152).** One helper, `engine/jobs/quotes.py`, finds a quote inside one
   field of a list (title, company, location, description), never across two, starting and
   ending on a word boundary and holding at least one letter or digit. `screen.flag` takes the
   list of fields; `eval_extract.verify` uses the same helper.
4. **Importance (F-148, F-149, F-152).** A must or nice word counts only when no negation
   (`gates.is_negated`) sits just before it. The word lists gain good to have, optional,
   extras, extra credit, would be a plus and what you need. An unrelated section heading
   (responsibilities, benefits, about us, what we offer, perks, how to apply, compensation)
   nearer than the nearest importance wording makes the importance unstated. A quote that
   appears more than once in its field states no importance. The marker is checked against
   the full field text, so a slice cannot fake a word end.
5. **Pay and caps (F-150, F-151).** `_amounts` applies a trailing `k` to both ends of a
   range (`3-4k`), and reads `3.000` and `3 000` as thousands. The 60-item caps on
   requirements and judgements become slices (the first 60) instead of a refused reply.
6. **Evaluation scope (F-153).** Both `select(Evaluation)` statements and the upsert filter on
   `user_id`.
7. **Tests (F-142 and the rest).** One test per repaired wording above; a route test for a
   flagged result (`removedBy` null); a failed re-run keeps an earlier flagged result; the
   long-posting test shows a flag from a quote in the part the model saw; the stale comment
   is reworded and the `hasattr` assertion replaced.

It must not break: clear gate removals, the flag rule (own dealbreaker plus a real quote),
the importance of well-formed postings ("Requirements" and "Nice to have" sections), owner
scoping, failure keeping the earlier result, and the no-logging rule.

## Build steps

- [x] 1. Gates (F-138): `gates.py` (location denial and list handling; public `is_negated`);
  tests in `test_job_gates.py`.
  **Done when:** `pytest tests/test_job_gates.py` passes, including "Nairobi (Remote work not
  allowed)", "Nairobi or Remote" and the clear cases, and the 200,000-character timing test.
- [x] 2. Migration (F-140, F-143): `0012_job_screen_gate_only.py`, `0010` downgrade, the model's
  check, `JobScreenOut.removed_by`, the web `removedBy` type; migration tests for a legacy
  `screen` row (converted to `flagged`, `screen` refused afterwards, downgrade restores) and
  for the `0010` downgrade clearing the reason; `tests/test_db.py` head `0012`.
  **Done when:** the table, db and screening tests pass and web typecheck passes.
- [x] 3. Quotes (F-141, F-152 part): `quotes.py`, `screen.flag` and `screening.py` to fields;
  tests in `test_job_quotes.py`, `test_job_screen.py`, `test_job_screening.py`.
  **Done when:** a quote across two fields, a quote starting mid-word and a punctuation-only
  quote are refused; a real quote in one field still flags.
- [x] 4. Importance (F-148, F-149, F-152): `eval_extract.py` per the fix above; tests in
  `test_eval_extract.py` for each wording the findings name and for well-formed postings.
  **Done when:** "Not required", "No requirements", "must not", "not a plus", "Good to have"
  under "Requirements", "Optional extras", "Responsibilities", a repeated quote and "mustard
  skills" with marker "must" all state nothing, and the common headings still state
  must or nice.
- [x] 5. Pay and caps (F-150, F-151): `_amounts`, the two caps; tests.
  **Done when:** "3-4k", "80-100k", "3.000" and "3 000" are read, a bare "3" with "4k" is not
  accepted, and 61 requirements and 61 judgements are cut, not refused.
- [x] 6. Scope and tests (F-153, F-142): user filters in `evaluating.py`; the F-142 test and
  comment repairs; a route test for a flagged result.
  **Done when:** `pytest` for the screen, evaluation and route tests passes.

## Verify

The `Verify` command from `AGENTS.md` must pass, then an independent review (a migration and
untrusted text going to a model). No screen is involved, so no browser check. The review
closes each finding or reopens it with evidence.

## Notes

- Baseline on `main` at `1097663` (this session): web 209 passed and 1 skipped; engine 668
  passed and 10 skipped; lint, typecheck and build pass.
- Only repairs the findings name. Do not widen into 8c or add features.

## Step notes

**Built (2026-11-11):** `gates.py` (location denial words; public `is_negated`); migration `0012_job_screen_gate_only.py`, the `0010` downgrade, the model check, `JobScreenOut.removed_by` and the web `removedBy` type; `jobs/quotes.py` (one field, word boundaries, a letter or digit) used by `screen.flag` and `eval_extract.verify`; `eval_extract.py` (negation, extended word lists, unrelated sections, repeated quotes, marker checked on the whole field, pay readings for `3-4k`, `3.000` and `3 000`, 60-item slices); `eval_evidence.py` (the same slice); `evaluating.py` (user filters); tests for every repaired wording.

**Decisions made while building**

- Old screen removals are converted to flags, not deleted and not left as removals: they stay visible with their quote and reason.
- A marker or occurrence with any negator (not, no, non, never, without, n't) states nothing; this errs toward `inferred`, which only lowers importance, never raises it.
- A quote that occurs more than once in its field states no importance.
- A model reply that gives more than 60 entries is cut to the first 60 (and 20 after verification), not refused.

**Repair round 1 (after the independent review requested changes):** F-154 (P1) a denial on an earlier line hid the next heading: `fold` now keeps line breaks and `is_negated` is scoped to the same line or sentence; F-155 the rewritten number readings refused `75,000.00`, `3,000.50`, `3.000,00` and `80,000-100k`: `_readings` now reads US and European styles. F-148 and F-150 were reopened by those two and are repaired by them. This was the second repair attempt for F-148.

**Verify (this session):** web lint, typecheck and build pass, web tests 209 passed and 1 skipped; engine ruff, format check and mypy pass, engine tests 744 passed and 10 skipped (668 before the cleanup, 723 before the repair round). No live model call and no browser check (no screen).



<!-- blueprint:completion {"schemaVersion":2,"specBytes":9042,"specSha256":"6182010d3484d108bcfd387bd8496fc5543ba1975d42467bb533ee0a061914e8","branch":"refs/heads/fix/clean-up-open-review-findings","head":"a101fc9c6a2f3d2ac67730dbbf0f3e2104626f82","baseRef":"refs/heads/main","baseCommit":"10976637279a49374d8bff08ccdbb2f89cbbf1f7","sourceTree":"d8ae460e6e979877c25ac8fd8740af0459d27e7c","landing":"local-merge","absentOptional":[]} -->

## Findings

### clean-up-open-review-findings/F-138 [P2] closed - A location that offers remote as an alternative removes an on-site-only track

**File:** engine/src/engine/jobs/gates.py:126
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality)
**Why it matters:** `_modes_stated` counts a bare `remote`, `hybrid` or `on-site` in the location field. Probed on an on-site-only track: location "Nairobi or Remote" and "Nairobi / Remote" return `work_mode`, although the job offers on-site work; "Nairobi (Remote work not allowed)" also removes because `_LIMITED` only catches a denial right after the word. A wrongly removed job is the outcome the spec rules out. The repair added negation to this field but not the list/alternative case that the region check already handles with `_LISTED`.
**Suggested fix:** Skip a location mode that is one item of a list or alternative ("or", "/", "," before or after), and treat a denial anywhere in the same parenthesis as unclear; add tests.
**Resolution:** Repaired 2026-11-11: a location that offers choices (`or`, `and`, `/`, `&`) next to a mode word makes the whole posting unclear, so the gate keeps the job. Tests: five offer wordings for on-site-only and remote-only tracks, and that `Remote, EMEA`, `On-site` and `Hybrid` still remove.
Repaired again: Repaired 2026-11-11 (fix `clean-up-open-review-findings`): a location that also holds a denial word (not, no, never, without, n't) is unclear, like one that offers choices; `Nairobi (Remote work not allowed)`, `Nairobi - no remote work` and `Remote working isn't possible` keep the job, `Nairobi, Kenya (Remote)` and `On-site, Nairobi` still remove. Tests in `test_job_gates.py`.
Reopened 2026-11-11 by independent review (fresh subagent): the list wording is fixed (probed "Nairobi or Remote", "Remote / Hybrid", "remote OR on-site": kept), but the other wording named in the original finding still removes. Probe of `run_gates` on an on-site-only track: location "Nairobi (Remote work not allowed)" returns `work_mode` (removal), because `_stated` only skips a denial immediately after the word (`_LIMITED`, gates.py:68/83) and the new `_OFFERS` mark does not apply. A job that says remote is not allowed is on-site, so the removal is wrong. No test covers it. Suggested fix: treat a denial anywhere in the same parenthesis or clause as unclear and add the test.
Closed 2026-11-11 by independent review (fresh subagent, current delta abb5c82): probed `_modes_stated` on 16 locations: "Nairobi (Remote work not allowed)", "Remote (no travel)", "Nairobi (onsite, no remote)" give `unclear`; "Remote", "Remote, EMEA", "On-site", "Hybrid", "Nairobi - On-site only" still give one mode; 200,000-character input runs in 0.01 s. The denial rule only adds `unclear`, so it can only keep more jobs.

### clean-up-open-review-findings/F-140 [P2] closed - Rows removed by the old screen stay removed, and `screen` is still an allowed remover

**File:** engine/migrations/versions/0010_job_screen_flagged.py:21, engine/src/engine/models.py:378, web/src/lib/jobs-api.ts:106
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, security)
**Why it matters:** The decision is that only a code gate removes a job, and the spec (step 4) says `removedBy` stays `'gate' | null`. But `upgrade` only swaps the outcome check: any `job_screen` row already written by the old word-matching (`outcome = 'removed'`, `removed_by = 'screen'`) is kept as a removal. `rules_key` does not include the prompt or rule version, so such a row is not `stale` and nothing re-screens it; it is exactly the wrong-removal class F-133, F-137 and F-139 recorded. `ck_job_screen_removed_by` still allows `'screen'`, `JobScreenOut.removed_by` is a free string, and the web `JobScreen.removedBy` type is still `'gate' | 'screen' | null`, so the contract still describes a screen removal. The new migration test seeds only a `gate` row, so this path is untested.
**Suggested fix:** In 0010 `upgrade`, convert `removed`/`screen` rows (to `flagged`, keeping their reason with the new wording, or to `unscreened` so they are re-run) before narrowing; tighten `ck_job_screen_removed_by` to `('gate')` in the migration and model; change the web type to `'gate' | null`; add a migration test with a legacy `screen` row.
**Resolution:** Repaired 2026-11-11: migration `0012_job_screen_gate_only` turns old screen removals into flags (outcome `flagged`, no remover, `Possible match for your dealbreaker ...` reason) and narrows `ck_job_screen_removed_by` to `gate`; the model, `JobScreenOut.removed_by` (`Literal['gate'] | None`) and the web `removedBy` type follow. Tests: a legacy row converts, `screen` is refused afterwards, the downgrade restores the wider check.
Closed 2026-11-11 by independent review (fresh subagent, current delta abb5c82): 0012 is one UPDATE that sets `outcome = flagged` and `removed_by = null` together, so `ck_job_screen_removed` holds at every row; the regexp matches the exact old `You ruled out ` prefix written by commits beb0de0 and later; constraint name and text agree in 0012, `models.py` and the web type; `removedBy` is read nowhere else. `test_a_removal_by_the_old_screen_becomes_a_flag` and the downgrade test pass against Postgres (engine suite 723 passed).

### clean-up-open-review-findings/F-141 [P3] closed - A flag can show a "posting says" quote that spans two fields or is only punctuation

**File:** engine/src/engine/jobs/screening.py:213, engine/src/engine/jobs/screen.py:164
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security)
**Why it matters:** The spec's honesty rule is that a shown quote is a stretch of the title, company, location or description. `_decide` joins the four fields with ". " and `flag` searches that joined text, so a model quote such as "Acme. Eng" (end of company plus ". " plus start of title) passes although no field contains it. The 6-character minimum is measured after folding, so a quote of "......" also passes when the posting contains it. Probed with `flag`: both return a `Flag`. Impact is low (nothing is removed; the user sees a odd quote) and no text outside the posting can appear.
**Suggested fix:** Check the quote against each field separately (any one containing it), and require at least one letter or digit in the quote.
**Resolution:** Repaired 2026-11-11: `engine/jobs/quotes.py` finds a quote inside one field only, on word boundaries and with at least one letter or digit; `screen.flag` and `screening.py` check each field separately. Tests in `test_job_quotes.py` and `test_job_screen.py` (across two fields, mid-word, punctuation only, title and location quotes).
Closed 2026-11-11 by independent review (fresh subagent, current delta abb5c82): `quotes.locate` checks one field at a time, on word boundaries, needing a letter or digit; `screening._decide` passes the four fields separately. Tests for two-field, mid-word and punctuation-only quotes pass; probed quote `......` and `Engineer Acme` refused.

### clean-up-open-review-findings/F-142 [P3] closed - Stale comment and tests that do not prove what they claim in the flag change

**File:** engine/src/engine/jobs/screening.py:213, engine/tests/test_job_screen.py:124, engine/tests/test_job_screen_routes.py:62
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, tests)
**Why it matters:** (1) The comment "Joined with a full stop so a denial in one field cannot spill into the next" describes the deleted negation check; the join now only separates fields. (2) `assert not hasattr(found, "removed")` is true of any dataclass without that attribute and proves nothing; the real proof is the service-level test. (3) No test makes a `flagged` row go through the route and `JobScreenOut` (the route test only covers a gate removal), and `test_a_failed_rerun_does_not_erase_an_earlier_result` starts from a `passed` row, so the rule that a failed re-run keeps an earlier `flagged` result is not tested. (4) `test_a_very_long_posting_is_cut_for_the_model_but_checked_whole` now asserts a flag from a quote the model could not have seen; it no longer matches a real model's behaviour.
**Suggested fix:** Reword the comment, replace the hasattr assertion with a route-level check that a flagged result has `removedBy` null, and add a flagged-then-failed-rerun test.
**Resolution:** Repaired 2026-11-11: the stale comment is gone with the joined text; the `hasattr` test is replaced by a possible-match test; a route test shows a flagged row with `removedBy` null; a failed re-run over a flag keeps it and shows it stale; the long-posting test now puts the quote in the part the model reads.
Closed 2026-11-11 by independent review (fresh subagent, current delta abb5c82): the stale comment is gone with the joined text; the `hasattr` test is replaced by an assertion on the reason; a route test goes through `JobScreenOut` with `removedBy` null; a failed re-run over a flag keeps it and shows it stale; the long-posting test asserts the quote sits in what the model read.

### clean-up-open-review-findings/F-143 [P3] closed - Downgrade turns a flag into a `passed` row that still carries the flag reason

**File:** engine/migrations/versions/0010_job_screen_flagged.py:29
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality)
**Why it matters:** `downgrade` sets `outcome = 'passed'` for flagged rows but leaves `reason_code = 'dealbreaker'` and the "Possible match" reason, so a `passed` row has a dealbreaker reason, a state the 0009-era code never wrote. The signal is also lost silently. The constraint swap itself is correct and the test shows rows survive.
**Suggested fix:** Also clear `reason_code` and `reason` for those rows (or map them to `unscreened` with a re-run reason).
**Resolution:** Repaired 2026-11-11: the `0010` downgrade clears `reason_code` and `reason` on the rows it turns into `passed`; a test checks it.
Closed 2026-11-11 by independent review (fresh subagent, current delta abb5c82): the 0010 downgrade now clears `reason_code` and `reason`; the table test asserts `(None, None)` on the downgraded row.

### clean-up-open-review-findings/F-149 [P2] closed - Importance is overstated as `must` under a heading the word lists do not know ("Good to have", "Optional"); the nearest wording is never reset by a new section

**File:** engine/src/engine/jobs/eval_extract.py:166, engine/src/engine/jobs/eval_extract.py:197
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** The lists miss common optional headings (good to have, optional, extra credit, would be great) and only wording before the quote is read. Probed: "Requirements\n- Flutter experience\nGood to have\n- Kubernetes experience" with the model saying `nice` and marker `Requirements` gives `must`/`posting` (also under "Optional extras" and under "Responsibilities"). Because a passing marker replaces the model's own importance, a sloppy or injected model reply makes an optional item a stated must-have, which is the F-144 outcome through a different door. In the other direction, trailing wording ("... is a plus", "Python is required") and headings such as "Qualifications", "What you bring" state nothing (probed: `inferred`, capped at `important`), so real must-haves are shown as important in common postings.
**Suggested fix:** Treat any heading-like line (short line ending a section, or a known section title such as Responsibilities, Benefits, Good to have, Optional) as resetting the nearest wording so the marker must agree with the section the quote sits in; extend the nice list; consider letting the model's own `nice` win over a stated `must` when the nearest wording is not a recognised heading. Add tests for these headings.
**Resolution:** Repaired 2026-11-11: the word lists gain good to have, optional, extras, extra credit, would be a plus or great and what you need; an unrelated section (responsibilities, benefits, perks, about us, what we offer, how to apply, compensation, ...) nearer than the importance wording makes the importance unstated. Tests: a new section replaces the importance above it, optional headings, unrelated sections, and the common headings still state must or nice.
Closed 2026-11-11 by independent review (fresh subagent, current delta abb5c82): "Good to have", "Optional extras", "Extra credit", "Bonus points" and the unrelated sections (Responsibilities, Benefits, About us, What we offer, How to apply) behave as specified (tests pass; probed). The remaining way to state `must` under a nice heading comes from the negation skip added for F-148, recorded as F-154.

### clean-up-open-review-findings/F-150 [P3] closed - A shared-suffix pay range ("3-4k", "80-100k") either drops the pay or accepts a bare "3"

**File:** engine/src/engine/jobs/eval_extract.py:216
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, tests)
**Why it matters:** `_amounts` applies the `k` only to the number it touches. For the quote "pay 3-4k per month" the read amounts are {3, 4000}: a faithful reply (min 3000, max 4000) is dropped, while min 3 with max 4000 is kept. "80-100k" gives {80, 100000}, so 80000 to 100000 is dropped. Probed with `_pay`. The result is only a missing salary check (honest `unknown`) or a wrong minimum that the band never reads, so impact is low, but ranges like this are common. `3.000` (decimal point as a thousands separator) and `3 000` are also dropped. No test covers a shared suffix.
**Suggested fix:** Apply a trailing `k` to the earlier number of a `a-bk` range as well (or accept either reading), and add tests for `3-4k`, `80-100k`.
**Resolution:** Repaired 2026-11-11: `_amounts` closes both ends of a shared-suffix range (`3-4k`, `80-100k`, `80 to 100k`), reads `3.000` and `3 000` as thousands, and no longer accepts a bare `3` from `3-4k`. Tests for each.
Second repair 2026-11-11: the reviewed hole was the number formats the rewrite no longer read (F-155); see its resolution. `3-4k`, `80-100k`, `3.000` and `3 000` still read; a bare `3` from `3-4k` is still refused.
Reopened 2026-11-11 by independent review (fresh subagent, current delta abb5c82): `3-4k`, `80-100k`, `3.000` and `3 000` are read and a bare `3` is refused, but the rewrite refuses figures the old code accepted; see F-155 (`75,000.00` now yields no amount).
Closed 2026-11-11 by independent review (fresh subagent, delta a101fc9): probed `_amounts` on `3-4k` (3000, 4000), `80-100k`, `80,000-100k`, `3.5-4k`, `10k-12k`, `3.000`, `3 000`, `$3 000`, `3000`, `1.250.000`; a bare 3 from `3-4k` is refused; tests pass. The decimal rounding left from F-155 is tracked there.

### clean-up-open-review-findings/F-151 [P3] closed - Replies with more than 60 requirements or judgements are refused instead of cut

**File:** engine/src/engine/jobs/eval_extract.py:70, engine/src/engine/jobs/eval_evidence.py:153
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality)
**Why it matters:** `ExtractOutput.requirements` and `EvidenceOutput.judgements` have `max_length=60`. The spec keeps at most 20 requirements and `verify` already slices to 20, but a reply with 61 or more entries fails validation (probed), costing a retry and then `ai_output_invalid` (502), the same class as F-147. Rare, but a long posting with a verbose model can reach it.
**Suggested fix:** Drop the field caps and slice in a `BeforeValidator` (as done for labels) or in `verify`.
**Resolution:** Repaired 2026-11-11: the 60-item caps on requirements and judgements are slices before validation, so a long reply is cut, not refused. Tests with 61 entries each.
Closed 2026-11-11 by independent review (fresh subagent, current delta abb5c82): `ExtractOutput` and `EvidenceOutput` cut a list to its first 60 in a `BeforeValidator`; `test_more_than_sixty_requirements_are_cut_not_refused` and the evidence test pass. (The same helper is written twice, in `eval_extract.py` and `eval_evidence.py`; noted only.)

### clean-up-open-review-findings/F-152 [P3] closed - A quote may span two posting fields, and importance is read where the quote first appears

**File:** engine/src/engine/jobs/eval_extract.py:150, engine/src/engine/jobs/eval_extract.py:261
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality)
**Why it matters:** `posting_text` joins title, company, location and description with newlines and `_fold` turns them into spaces, so a "verbatim quote" such as the end of the company plus the start of the description passes, although the spec says a quote must be a stretch of one field (same class as F-141). Also `text.find(quote)` takes the first occurrence, and the quote need not start at a word start: probed, posting "mustard skills", quote "ard skills", marker `must` gives `must`/`posting` because the marker check slices the text at the quote and `(?!\w)` is true at the end of the slice. A short repeated quote under a Requirements heading can likewise lend that heading to a nice item that is quoted elsewhere.
**Suggested fix:** Verify the quote against each field separately and require it to start on a word boundary; check the marker with the following character of the full text, not the slice; prefer the occurrence nearest the first marker.
**Resolution:** Repaired 2026-11-11: quotes are located inside one field on word boundaries, importance is read in that field, the marker is checked against the whole field (not a slice), and a quote that occurs more than once states no importance. Tests: across two fields, `ard skills` in `mustard skills`, marker `must` inside `mustard`, a repeated quote.
Closed 2026-11-11 by independent review (fresh subagent, current delta abb5c82): quotes are located inside one field, `ard skills` in `mustard skills` is dropped, marker `must` inside `mustard` states nothing, a quote occurring twice states nothing, and the marker is matched in the whole folded field. Probed performance on 12,000-character posts with 60 requirements: under 0.25 s.

### clean-up-open-review-findings/F-153 [P3] closed - Evaluation lookups and the upsert do not filter on user_id

**File:** engine/src/engine/jobs/evaluating.py:177, engine/src/engine/jobs/evaluating.py:274
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality)
**Why it matters:** The spec says every statement filters on `user_id`, and the coding standards require every user-owned query to be scoped. The two `select(Evaluation)` statements filter only on job and track, and the upsert conflicts on `(job_id, track_id)` without a user check. In practice the job and track were already proven to belong to the user, so no other user's row is reachable today; it is defense in depth and a standards drift that a later change to the unique key would expose.
**Suggested fix:** Add `Evaluation.user_id == user_id` to both selects and a `where` on the conflict update.
**Resolution:** Repaired 2026-11-11: both `select(Evaluation)` statements filter on `user_id` and the upsert replaces only a row of the same user. Test: another user's row at the same job and track is neither read as a cache hit nor replaced.
Closed 2026-11-11 by independent review (fresh subagent, current delta abb5c82): both selects and the upsert `where` carry `user_id`; the conflict update with a non-matching `where` updates nothing and the following select finds no row, so the call ends in `not_found` with the other user's row untouched (test passes). The model calls have been spent by then, which is acceptable for a state that cannot arise through owned jobs and tracks.

## Independent review

**Status:** passed
**Target commit:** a101fc9c6a2f3d2ac67730dbbf0f3e2104626f82
**Base commit:** 10976637279a49374d8bff08ccdbb2f89cbbf1f7
**Base ref:** main
**Spec hash:** 6182010d3484d108bcfd387bd8496fc5543ba1975d42467bb533ee0a061914e8
**Prepared by:** claude
**Builder model:** claude-fable-5-2
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T09:05:12Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T09:12:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `sha256sum blueprint/context/current-feature.md`, `git status --short`: pass (all match the request; only the two evidence files differ)
- `cd engine && uv run --env-file ../.env pytest -q`: pass (744 passed, 10 skipped)
- `cd engine && uv run ruff check .`: pass
- `cd engine && uv run mypy`: pass (108 source files)
- Scratch probes of `fold`, `occurrences`, `is_negated`, `_stated_importance`, `_amounts` under /tmp/rv (outside the repo): run, no repo writes
- Web lint, typecheck and tests: not run (the web delta is one type literal; engine route tests cover the `removedBy` values)

## Evidence

- Delta `10976637..a101fc9c` read in full: gates.py, quotes.py, screen.py, screening.py, eval_extract.py, eval_evidence.py, evaluating.py, migrations 0010 and 0012, models.py, the web type and the tests.
- Closed by re-examination: F-150 (`3-4k`, `80-100k`, `80,000-100k`, `3.5-4k`, `3.000`, `3 000` probed). Reopened: F-148, F-154 (line-break side effect of the `fold` change, new F-156) and F-155 (decimal rounding still present). F-154 lowered from P1 to P2 (original case gone; the remaining hole needs a phrase split over a wrapped line).
- Probes confirmed: wrapped "Nice to\nhave", "What we\noffer" and "Not\nrequired" no longer reset or negate (F-156); "What you'll do" after "Requirements" states `must` (F-157); `$13.50` yields 14 (F-155). Quotes and dealbreakers are whitespace-collapsed by `_clean` before `fold`, so the kept "\n" never reaches a quote or dealbreaker equality; `\r\n`, U+2028/2029 and tabs fold correctly; multi-line quotes still match; regex cost on 12,000-character fields is small (quotes are capped at 200 characters before `_amounts`).
- Migration 0012: update pairs outcome and remover so `ck_job_screen_removed` holds at every row; check narrowed; downgrade restores the wider check; 0010 downgrade clears reason (migration tests pass). `user_id` filters present on both selects and the upsert `where`.

## Findings

- New: F-156 (P2, line-break side effect of `fold` on the importance rule), F-157 (P3, missing section headings and trailing "must not").
- Reopened: F-148 (P2), F-154 (P2, was P1), F-155 (P3). Closed: F-150.
- No P0 or P1 is open or fixed.

## Remaining risk

- Wrapped headings or denials can still state `must` for an optional item (F-156) until repaired; this is the third round on the importance rule and the same hole class keeps reappearing.
- Pay figures with a decimal can be refused or off by one (F-155).
- The route test for a flagged result seeds the row with SQL and tests serialization only; the screening path to a flagged row is covered by the screening tests.
- Web lint, typecheck and tests were not run by this review.
