# Fix: Stop reading importance from the posting

**Type:** Fix
**Status:** verified
**Branch:** fix/stop-reading-importance-from-the-posting
**Fixes:** F-148, F-154, F-155, F-156, F-157, F-158, F-159, F-160, F-161, F-162, F-163, F-164, F-165, F-166, F-167

## The problem

Five review rounds on the rule that reads a requirement's importance (must or nice) from a
job posting's wording and headings kept finding holes of one kind: reading prose structure
with rules leaks, and each repair opened another (F-148 to F-167). The user decided on
2026-11-11: **stop reading importance from the posting.** The app never claims that a
posting states "must". F-155 (pay figures with cents were rounded up) is part of the same
branch and is repaired (cents read as their whole part).

## The fix

1. **Delete `eval_headings.py` and its tests.** The heading, label and wording readers go;
   so do `fields_of`'s description marker, `unique` and `in_text` plumbing in
   `eval_extract.py`.
2. **Importance is the model's guess, capped.** The extraction task asks for `important`
   or `nice`; a reply of `must` is read as `important`. A requirement is `important` or
   `nice`, never `must`, so the posting is never said to have stated it. The prompt
   becomes `eval-extract-3`.
3. **Drop `importanceSource`** from the stored requirement, the engine output
   (`RequirementOut`), the web type and the spec contract: with one source it says
   nothing. Rows already saved keep working (the extra key is ignored on read).
4. **The band is unchanged in code.** `eval_band` still takes `must`, `important` and
   `nice`. With no `must` ever produced, the deciding requirements are the `important`
   ones, and the summary reads "Evidence for 4 of 6 important requirements". The
   must-have rule becomes live again only if importance is ever set by a user or a better
   reader; 8d's golden set tunes the thresholds against the founder's own verdicts.
5. **Keep** the one-field quote rule, line-preserving `fold`, the pay readings and the
   cents rule, owner scoping and the no-logging rule.

## Build steps

- [x] 1. Delete `eval_headings.py` and `test_eval_headings.py`; simplify `eval_extract.py`
  (cap `must` to `important`, no section reading, no source), bump the prompt to
  `eval-extract-3`; rewrite the importance tests in `tests/test_eval_extract.py`.
  **Done when:** the extraction tests pass; no test or source mentions headings, a
  marker or an importance source; `must` in a model reply becomes `important`.
- [x] 2. Remove `importance_source` from `evaluating.py`, `RequirementOut` and the stored
  JSON, and `importanceSource` from `web/src/lib/jobs-api.ts`; update
  `test_evaluating.py` and `test_evaluation_routes.py`.
  **Done when:** engine and web tests, lint and typecheck pass, and the route shape test
  lists no `importanceSource`.

## Verify

The `Verify` command from `AGENTS.md` must pass, then an independent review (model output
decides what the user is shown). No screen, so no browser check.

## Notes

- Baseline on `main` at `55b6e4d` (this session): web 209 passed and 1 skipped; engine 744
  passed and 10 skipped. The branch carries the heading reader as `d15c16d`, which this
  fix deletes; the cents rule from the same branch stays.
- The headings reader, its findings (F-148, F-154 to F-167) and their repairs stay in the
  history; this fix makes them moot by removing the code they were about.

## Step notes

**Built (2026-11-11):** `eval_headings.py` and its tests are deleted; `eval_extract.py` no longer reads headings, labels or wording: a requirement's importance is the model's guess, with `must` read as `important` (prompt `eval-extract-3`, which asks only for `important` or `nice`); `importance_source` / `importanceSource` are removed from the engine output, the stored requirement and the web type; the web `Importance` type is `important | nice`; the evaluation tests assert that a `must` from the model reads as `important`. The one-field quote rule, line-preserving `fold`, the pay readings and the cents rule stay.

**Decision:** the user chose on 2026-11-11 to stop reading importance from the posting after five review rounds on that reader. With no `must` ever produced, the band's deciding requirements are the `important` ones; the band code is unchanged and 8d's golden set tunes it.

**Verify (this session):** web lint, typecheck and build pass, web tests 209 passed and 1 skipped; engine ruff, format check and mypy pass, engine tests 714 passed and 10 skipped (the heading reader's tests are gone). No live model call and no browser check (no screen).



<!-- blueprint:completion {"schemaVersion":2,"specBytes":4613,"specSha256":"a1a411392c0bf20047821a85f4eaeb2fdf48396f033628c8a7475fba910f5d17","branch":"refs/heads/fix/stop-reading-importance-from-the-posting","head":"e163dd953fa4500ce729980d8651f15e87c3375b","baseRef":"refs/heads/main","baseCommit":"55b6e4def3127c6c51a96549910d6da5db60f56e","sourceTree":"4eb5e64940de50057cc1d56057b91e408235eb3f","landing":"local-merge","absentOptional":[]} -->

## Findings

### stop-reading-importance-from-the-posting/F-148 [P2] closed - A negated importance wording ("Not required", "No requirements", "must not") still states a must-have

**File:** engine/src/engine/jobs/eval_extract.py:166
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** `_MUST_WORDS` and `_NICE_WORDS` are plain word matches with no look at what comes before them. Probed with `verify`: posting "Not required: Kubernetes experience" with marker `Not required` gives `must`/`posting`; the same for "No requirements for: ..." (marker `No requirements`), "You must not need: ..." (marker `must not`), and `nice` for "Not a plus: ..." (marker `a plus`). The nearest-wording check also treats such a phrase as a heading. A negated or taken-back wording therefore turns an item into a stated must-have, which feeds the band, and the posting's own words said the opposite. `gates.py` already has `_NEGATION` for exactly this and is not used here. No test covers a negated wording.
**Suggested fix:** Ignore a must or nice word that has a negation just before it (reuse `gates._NEGATION`) both in the marker and in the nearest-wording search, so such a marker states nothing; add tests for `Not required`, `No requirements`, `must not`, `not a plus`.
**Resolution:** Repaired 2026-11-11: a marker containing a negation, or a marker occurrence with a negation just before it, states nothing, and negated must or nice words are skipped in the nearest-wording scan. Tests: `Not required`, `No requirements`, `must not`, `Not a plus`, `Never optional`, each with every claimed importance.
Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording.
Fourth repair 2026-11-11 (the user approved the rewrite past the repair limit, then a further inversion of the section rule after the review of the rewrite): `Not required:` and every negated label or heading states nothing, by label or by the run rule, with tests for the label on the same line, on a wrapped line and as a heading.
Third repair 2026-11-11 (fix `read-importance-by-headings`, approved by the user past the repair limit): the rule is rewritten. Importance comes only from the nearest heading line above a requirement, read by lines in `eval_headings.py`; there is no character window, and a negated or mixed heading is simply a heading of another kind. `Not required:`, `No requirements` and `Required or nice to have` all state nothing. Tests in `test_eval_headings.py` and `test_eval_extract.py`.
Second repair 2026-11-11: the reviewed hole was the negation window crossing a line break (F-154); it is now scoped to the same line or sentence. Re-test: all the original wordings still state nothing and a denial on an earlier line no longer hides a heading.
Reopened 2026-11-11 by independent review (fresh subagent, current delta abb5c82): the original defect is gone ("Not required", "No requirements", "must not", "not a plus" now state nothing), but skipping a negated wording in `_wording` (eval_extract.py:197) introduced a new bypass, recorded as F-154 (a negation just before a "Nice to have" heading hides that heading, so the older "Requirements" marker states `must`).
Reopened 2026-11-11 by independent review (fresh subagent, delta a101fc9): the F-154 repair cut `is_negated` at a line break, so a denial split over two lines no longer counts. Probed `verify`: description "Not\nrequired: Kubernetes experience", marker `required`, quote "Kubernetes experience" returns `must`/`posting`; the one-line "Not required: ..." returns `inferred`. The original wordings on one line are all fixed; see F-156 for the line-break defect.
Reopened 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..346b3cb): the heading-line wordings (`Not required:`, `No requirements`) are now headings of another kind, but the same denial with its text on the same line still states `must`. Probed `section_of`: "Requirements\n- Python\n- Not required: Kubernetes experience" and the unbulleted form both return `must` for "Kubernetes experience" because `_inline` returns None for a non-must/nice label and the lookup falls back to the Requirements heading. See F-160.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..d15c16d): re-examined eval_headings.py and eval_extract.py; probed `section_of`: "Not required: Kubernetes experience" and "No requirements for: Kubernetes" return `other` (state nothing); no negation window or marker remains. A different residual (a denial or hedge elsewhere on the item's own line, and a wrapped denial heading without a colon) is recorded as F-165 and F-166.

### stop-reading-importance-from-the-posting/F-154 [P2] closed - A negation just before a "Nice to have" heading hides it, so the "Requirements" marker states `must` for a nice-to-have item

**File:** engine/src/engine/jobs/eval_extract.py:197, engine/src/engine/jobs/eval_extract.py:229
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** `_wording` drops any must or nice word that `is_negated` (a "no", "not", "never", "without", "non" or "n't" in the 24 characters before it, up to two words and no sentence boundary). For a negated heading the intent is right, but a negation that belongs to the previous sentence also hides the next heading, so `nearest` falls back to the older "Requirements" and agrees with a marker the model chose. Probed with `verify`: description "Requirements\n- Python\nNo degree needed\nNice to have\n- Rust experience", quote "Rust experience", marker "Requirements", model claim `must` returns `must`/`posting` (the same text without the "No degree needed" line returns `important`/`inferred`). "Candidates from agencies: no thanks.\nNice to have" behaves the same way. A posting line such as "No degree needed" or "No agencies" before the nice-to-have section is common, and a sloppy or injected model reply then makes an optional item a stated must-have that feeds the band, the exact outcome the nearest-wording rule exists to stop (F-149, F-144). The tests cover a negated marker but never a negation that precedes a different heading. It also errs the other way for stated `nice`, which only lowers.
**Suggested fix:** Do not drop a negated wording from the nearest-wording scan; keep it as a position of its own kind so it resets the section (and only refuse to let a negated marker state anything). Also bound `is_negated` at a sentence or line break. Add tests for "No degree needed" and "no thanks." directly above a nice heading.
**Resolution:** Repaired 2026-11-11: `fold` keeps line breaks (matching ignores them, so wrapped quotes still match) and `gates.is_negated` looks only inside the same line or sentence, so a denial on an earlier line cannot hide the next heading. Tests: five denial lines (`No degree needed`, `no thanks.`, `Never mind`, `Not relevant here`, `No`) above `Nice to have`, a same-line denial that still states nothing, a denial in an earlier sentence that does not carry over, a quote wrapped over two lines.
Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording.
Repaired 2026-11-11: a denial line such as `No degree needed`, `no thanks.`, `Never mind` or `No` is an ordinary line, not a heading, so it cannot hide `Nice to have`; the nearest heading above decides. Tests for each denial line.
Reopened 2026-11-11 by independent review (fresh subagent, delta a101fc9), severity lowered from P1 to P2: the reported case is gone (a denial line such as "No degree needed" above "Nice to have" no longer hides it; probed, tests pass), but keeping the line breaks in `fold` made every multi-word wording pattern miss a phrase that wraps over a line. Probed `verify`: "Requirements\n- Python\n\nNice to\nhave\n- Rust" with marker `Requirements` and quote "Rust" returns `must`/`posting` (the unwrapped heading returns `inferred`); same for a wrapped "What we\noffer" and "How to\napply" (see F-156). The remaining hole needs a heading or phrase split over a line, so it is rarer than the original P1 case; it is the same outcome (a nice item stated as `must`) and the repair's own side effect.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..346b3cb): re-examined `eval_headings.classify` and `section_of`; probed "Requirements\n- Python\nNo degree needed\nNice to have\n- Rust" (also "no thanks.", "Never mind", "No") returns `nice`, and no must or nice word is ever skipped by a negation window any more. Engine tests pass.

### stop-reading-importance-from-the-posting/F-155 [P3] closed - The pay figure rewrite refuses `75,000.00`, and mixes the `k` of a range into a full figure

**File:** engine/src/engine/jobs/eval_extract.py:249
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, tests)
**Why it matters:** `_readings` accepts only whole thousands groups, one decimal of one or two digits, or plain digits. Probed `_amounts`: "USD 75,000.00 per year" and "$75,000.00" give no amount at all, as do "3,000.50" and "EUR 3.000,00"; the old code read "75,000.00" as 75000. A faithful reply with min 75000 is now dropped (the salary check becomes `unknown`), so a true figure is refused. "80,000-100k" reads the first end as 80,000,000 and drops the true 80000. "12,5" reads as 12 (`round` of 12.5). Impact is a missing salary check only, but the tests cover no decimal with a thousands separator, and the format is common in postings.
**Suggested fix:** Read a trailing `.dd` or `,dd` after a thousands-grouped number as cents, and apply the range `k` only to ends that are short (no thousands separator); add tests for `75,000.00`, `3.000,00` and `80,000-100k`.
**Resolution:** Repaired 2026-11-11: `_readings` reads US style (`75,000.00`, `3,000.50`, `3.5`) and European style (`3.000,00`, `3,5`), treats three digits after a separator as thousands (so `3,000` never reads as 3), and a shared `k` multiplies only a small number (`80,000-100k` reads 80000 and 100000). Tests for each format and for the wrong readings being refused.
Repaired 2026-11-11: a figure with cents reads as its whole part (`13.50` is 13), never rounded up, so a true 13 is accepted and an invented 14 is refused (`12.50`, `99.99`, `1,5` the same); float noise does not drop `1.1k`. Tests for each.
Reopened 2026-11-11 by independent review (fresh subagent, delta a101fc9): `75,000.00`, `3,000.50`, `3.000,00`, `80,000-100k` and `3,000` are now read correctly (probed, tests pass). The rounding named in the original text is still there and now misreads in both directions: `_amounts` rounds a decimal with Python's `round`, so `$13.50 per hour` yields {14} and `$12.50` yields {12}, `$99.99` yields {100}, `1,5` yields {2}, `$3.5 an hour` yields {4}. A faithful reply of 13 is refused and an invented 14 is accepted. Low impact (an hourly or small figure; the pay is dropped or off by one). Fix: accept both the floor and the rounded value, or refuse any decimal that is not a whole number after scaling.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..346b3cb): probed `_amounts`: `$13.50` gives {13}, `12.50` {12}, `99.99` {99}, `1,5` {1}, `75,000.00` {75000}, `3.000` {3000}, `3,5k` {3500}, `3-4k` {3000, 4000}, `4.35k` {4350}, `1.15k` {1150}; `_whole` absorbs float noise (4.35*100 gives 434.999.. and reads as 435). Rounded-up figures 14, 13, 100 and 2 are no longer produced.

### stop-reading-importance-from-the-posting/F-156 [P2] closed - Keeping line breaks in `fold` makes wrapped headings and denials invisible to the importance rule

**File:** engine/src/engine/jobs/eval_extract.py:167, engine/src/engine/jobs/eval_extract.py:184, engine/src/engine/jobs/quotes.py:13, engine/src/engine/jobs/gates.py:80
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, security, tests)
**Why it matters:** The F-154 repair made `fold` keep each line break as "\n" and made `is_negated` stop at it. `occurrences` was adapted to treat "\n" as a space, but the word lists in `eval_extract.py` (`nice[- ]to[- ]haves?`, `good to haves?`, `what you(?:'ll| will)? need`, `minimum qualifications?`, `extra credit`, `about (?:us|...)`, `what we offer`, `how to apply`) were not, and a space in those patterns no longer matches a wrapped line break. Probed with `_stated_importance`: "Requirements\n- Python\n\nNice to\nhave\n- Rust", marker `Requirements`, quote "Rust" returns `must` (the same text with the heading on one line returns None); a wrapped "What we\noffer" and "How to\napply" section also leave the earlier "Requirements" in force; "Not\nrequired: Kubernetes experience" with marker `required` returns `must` (one line returns None). Hard-wrapped postings (pasted from email or PDF) are the case; before the repair the collapsed spaces matched. A sloppy or injected model reply can then make an optional item a stated must-have, the outcome F-148, F-149 and F-154 exist to stop. No test wraps a heading or a negation.
**Suggested fix:** Match the word lists and `_NEGATION` against text where "\n" is a space (for example a second view, `folded.replace("\n", " ")`, with the same offsets, or `\s+` in the patterns), and treat a "\n" as a boundary only for `is_negated`'s denial scope when the line break is a real paragraph or list break (a lone wrapped break inside a sentence is not). Add tests for a wrapped "Nice to have", "What we offer" and "Not required".
**Resolution:** Repaired 2026-11-11: a heading wrapped over two short lines is read whole (`Nice to` / `have`, `What we` / `offer`, `How to` / `apply`), so a stale heading above no longer stands. Tests in both test files.
Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording.
Re-repaired 2026-11-11: a wrapped denial label (`Not` / `required: x`) and wrapped headings (`Nice to` / `have`) are joined and read whole; tests for both.
Reopened 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..346b3cb): wrapped `Nice to`/`have`, `What we`/`offer` and `How to`/`apply` headings are read whole (probed), but the denial wrapped over two lines still states `must`: "Not\nrequired: Kubernetes experience" returns `must` at eval_headings.py:93 (the second line is read as its own `required:` label and the denial line above is ignored). The original probe from this entry is unchanged. See F-160.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..d15c16d): probed `section_of`: "Requirements\n- Python\n\nNice to\nhave\n- Rust" returns `nice` and "Not\nrequired: Kubernetes experience" returns `other`. The wrapped denial that has no colon ("Not\nRequired") still reads `must`; recorded as F-166.

### stop-reading-importance-from-the-posting/F-157 [P3] closed - Common headings are missing from `_OTHER_SECTIONS`, and `must` followed by a negation still states a must

**File:** engine/src/engine/jobs/eval_extract.py:177, engine/src/engine/jobs/eval_extract.py:203
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality)
**Why it matters:** The unrelated-section list names responsibilities, benefits, perks, about us/the role/team/company, what we offer, how to apply, compensation, our values and interview process. Probed `_stated_importance`: "Requirements\n- Python\nWhat you'll do\n- Build payment systems", marker `Requirements`, quote "Build payment systems" returns `must`/`posting`, so a task under "What you'll do", "Your role", "Day to day", "Our stack" or "Why join us" after a Requirements section is stated as a must-have. Also, only a negation before a word is read: "Candidates must not need sponsorship: Python" with marker `must` (a bare word) still states `must`, though the spec lists "must not" as stating nothing (the test only passes the marker "must not"). In the safe direction, the list's words also match inside a bullet ("Experience with benefits tools"), which only lowers a later item to `inferred`.
**Suggested fix:** Extend the list with the common headings above and treat a "must" followed by "not" or "never" as negated. Add tests for them.
**Resolution:** Repaired 2026-11-11: `What you'll do`, `What you will do`, `Who we are`, `Why join us` and the tech stack headings are other-section headings, and any short line ending in a colon, any `#` line and any negated or mixed heading is a heading of another kind. The model's marker is gone from the prompt (`eval-extract-2`), so a bare `must` followed by `not` cannot state anything.
Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording.
Re-repaired 2026-11-11: `What you will do`, `Your role`, `Day to day`, `Our stack`, `About you`, `Qualifications` and `What you bring` are recognised as other headings, and any line that is not a recognised heading ends the run anyway. Tests for each.
Reopened 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..346b3cb): the resolution says `What you will do` is an other-section heading, but `classify` returns None for it (4 words, no colon, over MAX_WORDS=3), as for `Your role`, `Day to day`, `Our stack` and `About you`. Probed `section_of`: "Requirements\n- Python\nWhat you will do\n- Build payment systems" returns `must` for "Build payment systems" (also `Your role`, `Day to day`, `Our stack`). Only the apostrophe form `What you'll do` is tested. See F-159.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..d15c16d): probed `section_of`: "Requirements\n- Python\nWhat you will do\n- Build payment systems" returns `other`; `Your role`, `Qualifications` and an unknown heading end the run (`other` or None). The model's marker is gone (prompt eval-extract-2, test asserts it).

### stop-reading-importance-from-the-posting/F-158 [P1] closed - A "Heading: text" label stands over every later sentence of the same line, so a one-paragraph posting states the wrong importance

**File:** engine/src/engine/jobs/eval_headings.py:79
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** `_inline` reads only the first colon of the line (`stripped.find(":")`) and returns that label for any quote after it. A posting without line breaks, or any line with a second label, is read by the first one. Probed `section_of` on the folded text: "Requirements: Python, Go. Nice to have: Rust." with quote "Rust" returns `must`; "Required: Python. Nice to have: Go." with quote "Go" returns `must`; "Requirements: Python, Go. Responsibilities: build the payments engine." with quote "build the payments engine" returns `must`. A posting pasted as one paragraph (common for scraped or API descriptions) therefore states `must`/`posting` for a nice-to-have item or a task, with no model involvement beyond choosing the quote, and `must` feeds the band. This is the same sliding-label defect the rewrite set out to remove, moved from a character window to a line. No test uses a line with two labels.
**Suggested fix:** Use the nearest label before the quote on that line (the last colon whose label classifies as a heading before the quote's offset), and let a non-must/nice label there end the inline reading as `other`. Add tests for the three probes above.
**Resolution:** Repaired 2026-11-11: a `Label: text` quote takes its own nearest label on its own line, so `Requirements: Python, Go. Nice to have: Rust.` reads Rust as nice and `Responsibilities: build the payments engine` states nothing. Tests: one-paragraph postings, times such as `10:30` are not labels.
Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..d15c16d): probed the three original one-paragraph cases: "Requirements: Python, Go. Nice to have: Rust." gives `nice`, "Required: Python. Nice to have: Go." gives `nice`, "...Responsibilities: build the payments engine." gives `other`. The label still stands over later unlabeled sentences of the same line ("Requirements: Dart. The team also uses Kafka." gives `must`); recorded as F-164.

### stop-reading-importance-from-the-posting/F-159 [P1] closed - A heading the reader does not recognise does not end a section, so the heading above keeps standing over the wrong requirement

**File:** engine/src/engine/jobs/eval_headings.py:37
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** `classify` returns None (not a heading) for any line without a must, nice or other keyword unless it ends with a colon, and for anything over 3 words without a colon. `section_of` then keeps walking up to the older heading. Probed: "Requirements\n- Python\n<H>\n- Build payment systems" returns `must` for H in "What you will do", "Your role", "Day to day", "Our stack", "Why you'll love it here", "About you"; "Nice to have\n- Rust\nQualifications\n- Python 5y" returns `nice` (also for "About you" and "What you bring"), so a requirement of the must section is stated as nice and a task is stated as must. Real postings use these headings constantly (the spec itself names "What you'll do" after "Requirements"; only the apostrophe form is recognised and tested). The failure is not conservative: the posting is made to state `must` or `nice` under a heading it does not have. The spec's rule "any other nearest heading states nothing" cannot hold when other headings are not detected.
**Suggested fix:** Treat any short line that is not a list item, has no sentence punctuation and is followed by a list item or ends a paragraph as a heading of kind `other` (a heading of unknown kind), and add the common must/nice heading forms (`What you bring`, `About you`, `Qualifications`, `Skills & experience`) as explicit kinds or as `other`. Add tests for each heading in the probe lists, not only the apostrophe form.
**Resolution:** Repaired 2026-11-11: the section rule is inverted. A list item is inside a section only when every line between it and a recognised heading is also a list item; any other line (an unrecognised heading such as `Your role`, `Day to day`, `Our stack`, `About you`, `Qualifications`, `Life at Acme`) ends the run, so nothing a reader does not recognise leaves an older heading standing. Tests for each heading from the finding under both `Requirements` and `Nice to have`.
Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..d15c16d): probed "Requirements\n- Python\n<H>\n- Build x" for `Your role`, `Why you'll love it here`, `What you will do` and "Nice to have\n- Rust\nQualifications\n- Python 5y": an unrecognised or other heading line ends the run (None or `other`). The same stale-heading effect through a non-item quote line or a blank line is recorded as F-163.

### stop-reading-importance-from-the-posting/F-160 [P1] closed - A line "Not required: x", "Benefits: x" or "Responsibilities: x" falls back to the heading above and states `must` or `nice`

**File:** engine/src/engine/jobs/eval_headings.py:79
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** `_inline` returns a kind only for must or nice; an `other` label (including a negated one) returns None and `section_of` goes on to the nearest heading above. Probed: "Requirements\n- Python\n- Not required: Kubernetes experience" and the unbulleted line return `must` for "Kubernetes experience"; "Requirements\n- Python\nBenefits: free lunch" returns `must` for "free lunch"; "Responsibilities: Kubernetes operations" under Requirements returns `must`. A denial split over two lines ("Not\nrequired: Kubernetes experience") returns `must` because the line is read as `required:`. These are exactly the F-148 and F-156 wordings, so those repairs do not hold on the same-line form. A requirement the posting explicitly says is not required becomes a stated must-have.
**Suggested fix:** When the line has a heading-shaped label before the quote that classifies as `other` (including negated or mixed), return `other` instead of falling through, and treat a first line that follows a denial or wrapped label line (pair) before the colon the same way. Add tests for the four probes.
**Resolution:** Repaired 2026-11-11: an `other` or denial label on the quote's own line (`- Not required: x`, `Benefits: free lunch`, `Responsibilities: ...`) is the quote's section and states nothing; a denial wrapped over two lines (`Not` / `required: x`) is joined and states nothing. Tests for each.
Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..d15c16d): probed "Requirements\n- Python\n- Not required: Kubernetes experience", "Benefits: free lunch" under Requirements, and "Not\nrequired: Kubernetes experience": all return `other`.

### stop-reading-importance-from-the-posting/F-161 [P2] closed - A short requirement or benefit line is read as a heading, so it changes the importance of the lines after it

**File:** engine/src/engine/jobs/eval_headings.py:37
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** A heading is any non-bullet line of up to 3 words that contains a must or nice word, so an unbulleted item is a heading. Probed with `section_of`: "Responsibilities\nBuild APIs\nPython required\nKnowledge of Go" returns `must` for "Knowledge of Go"; "Requirements\nPython\nExperience preferred\nKnowledge of Go" returns `nice`; "About us\nWe sell things\nMust have Python\nA degree in biology" returns `must`; "Responsibilities\nGo\nrequired\nBuild things daily" returns `must` (two unrelated short lines paired by `_pair`); "Nice to have\n- Rust\nGo preferred\nKubernetes knowledge" returns `nice` for the line after. Plain-text postings (LinkedIn style, no bullets) are the case. The effect needs a requirement line of at most 3 words with an importance word followed by an item of another kind, so it is rarer than F-158 to F-160 but states importance the posting does not.
**Suggested fix:** Treat a short line as a heading only when it is followed by a list item or a blank-line break, or when it has no verb-like content; at minimum do not let a line that is itself an item of the section (same indentation, following another unbulleted item) change the section. Add tests for the probes above.
**Resolution:** Repaired 2026-11-11: only a heading that is exactly a known phrase is a must or nice heading, so `Python required`, `Experience preferred` and `Go preferred` are ordinary lines that end a run; adjacent real headings are not joined. Tests for each.
Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..d15c16d): probed "Responsibilities\nBuild APIs\nPython required\nKnowledge of Go" and "Requirements\nPython\nExperience preferred\nKnowledge of Go": both return None (a body line is not a heading). The line `required` alone is still a must heading (see F-166).

### stop-reading-importance-from-the-posting/F-162 [P3] closed - A test fixture still sends a `marker`, and the new tests do not cover the headings that real postings use

**File:** engine/tests/test_evaluating.py:64
**Found:** 2026-11-11 by /audit independent (scope: current; lens: tests)
**Why it matters:** The spec's step 2 says "no test mentions a marker"; `FakeProvider.extraction` still returns `"marker": "Requirements"` twice (ignored by `extra="ignore"`, so the test passes but documents a field that no longer exists). `test_eval_headings.py` and the extract tests cover only the apostrophe `What you'll do`, no line with two labels, no `Not required: x` on one line, no `About you`, `What you bring`, `Qualifications` or `Your role`, and no one-paragraph posting, which is why F-158 to F-161 passed all 777 tests. `test_a_long_posting_is_read_quickly` times only a posting whose heading sits near the top.
**Suggested fix:** Drop the `marker` keys from the fixture and add the probes from F-158 to F-161 as tests.
**Resolution:** Repaired 2026-11-11: the stale `marker` key is gone from the test fixture (no test sends one); the new tests cover one-paragraph postings, `What you will do`, `Your role`, `Day to day`, `Our stack`, `About you`, denial labels and wrapped denials.
Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording.
Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..d15c16d): no `marker` key remains in engine/tests (grep); test_eval_headings.py and test_eval_extract.py cover the probes of F-158 to F-161. Gaps that still let tests pass over F-163 to F-166: no test puts prose after a list or a blank line, a bulleted heading, an item that hedges itself, or a label followed by an unlabeled sentence.

### stop-reading-importance-from-the-posting/F-163 [P1] closed - A quote on a non-list line right after a list or a blank line inherits the heading above, so a paragraph states `must` or `nice`

**File:** engine/src/engine/jobs/eval_headings.py:140
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** The repaired rule says a run is unbroken only when every line between the quote and the heading is a list item, but `section_of` never checks that the quote's own line is an item, and its walk skips blank lines as well as items. Probed `section_of` on folded text: "Requirements\n- A\n- B\nWe also use Kafka daily." returns `must` for "Kafka"; "Requirements\n- A\n\nWe pay for Kafka training." returns `must`; "Requirements\n- A\n- B\n\nOur culture values Kafka expertise." returns `must`. A closing paragraph, a benefits sentence or a company blurb after the last bullet (with or without a blank line, and with no heading the reader knows) is stated by the posting as a must-have (or a nice-to-have), and `must` feeds the band. This is the F-159 outcome through a different gap, and the model only has to pick a quote from such a sentence. No test places prose after a list or after a blank line.
**Suggested fix:** In `section_of`, when the quote's own line is not a list item, accept a heading only when the quote is on the first line after that heading (blank lines allowed only directly between a heading and its first line); a blank line after at least one item, or a non-item quote line after items, ends the run and states nothing. Add tests for the three probes.
**Resolution:** Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording. Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..e163dd9): `eval_headings.py` is absent from engine/src/engine/jobs, `rg 'eval_headings|classify|marker|importance_source'` finds nothing in engine/src or tests, `eval_extract.verify` reads no text around the quote, and nothing worse replaced it (engine 714 passed, ruff and mypy clean).

### stop-reading-importance-from-the-posting/F-164 [P2] closed - A "Label: text" label stands over every later unlabeled sentence of the same line

**File:** engine/src/engine/jobs/eval_headings.py:103
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** `_label_before` takes the last label before the quote on the line with no regard to sentence breaks, so text after the labelled clause keeps the label. Probed: "Requirements: Dart. The team also uses Kafka." returns `must` for "Kafka"; "Skills: A. Requirements: Dart. We offer Kafka training and free lunch." returns `must` for "Kafka"; "Nice to have: Rust. We need Python for payments." returns `nice` for "Python" (a mis-lowering). One-paragraph postings (descriptions with line breaks stripped) are exactly where the label rule is used. F-158's three original probes are fixed; this is the same defect for text without its own label.
**Suggested fix:** End a label's reach at the next sentence end (". ", "! ", "? ") before the quote unless the text between is a list continuation (a comma or "and"); when a sentence boundary lies between label and quote, state nothing. Add tests for the probes.
**Resolution:** Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording. Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..e163dd9): `eval_headings.py` is absent from engine/src/engine/jobs, `rg 'eval_headings|classify|marker|importance_source'` finds nothing in engine/src or tests, `eval_extract.verify` reads no text around the quote, and nothing worse replaced it (engine 714 passed, ruff and mypy clean).

### stop-reading-importance-from-the-posting/F-165 [P2] closed - A list item that hedges or denies itself ("(nice to have)", "is a plus", "is not required") under Requirements still states `must`

**File:** engine/src/engine/jobs/eval_headings.py:122
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** The reader looks only at headings and a label before the quote. Probed: "Requirements\n- Python\n- Kubernetes (nice to have)", "Requirements\n- Rust is a plus" and "Requirements\n- Java is not required" each return `must` for the quoted skill, with source `posting`, although the item's own line says the opposite. The posting-states-must outcome comes from the heading, but the posting did not put the item in the must section. Inline "(nice to have)", "(preferred)", "is a plus" and "not required" inside a Requirements list are common. Likewise a quote that starts in a must item and spans a following nice item ("Python - Nice to have - Rust") is read at its start only. The pre-rewrite code had the same gap after the quote, but the spec's goal and the brief's states-nothing-by-default rule now make it a miss.
**Suggested fix:** Treat the quote's own line (and the rest of the quote) as a boundary: if the line, outside the quote's start, holds a nice, must or denial wording (`nice to have`, `preferred`, `a plus`, `optional`, `not required`, `no ... needed`) or the quote spans a label, state nothing. Add tests.
**Resolution:** Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording. Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..e163dd9): `eval_headings.py` is absent from engine/src/engine/jobs, `rg 'eval_headings|classify|marker|importance_source'` finds nothing in engine/src or tests, `eval_extract.verify` reads no text around the quote, and nothing worse replaced it (engine 714 passed, ruff and mypy clean).

### stop-reading-importance-from-the-posting/F-166 [P2] closed - A bulleted or numbered heading ("- Nice to have", "2. Nice to have:", "* **Nice to have**") is not a heading, so its items state `must`

**File:** engine/src/engine/jobs/eval_headings.py:60
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** `classify` returns None for any list item, so a heading written as a list item is skipped and the heading above stands. Probed `section_of`: "Requirements\n- Python\n- Nice to have\n  - Rust" returns `must` for "Rust" (also "- Nice to have:", "* **Nice to have**\n- Rust", "2. Nice to have\n3. Rust"); a nice item is stated as a must. Markdown and LLM-formatted postings nest "Nice to have" under a bullet routinely. Separately, a wrapped denial heading without a colon is read by its second line alone: "Not\nRequired\n- Python", "No\nRequirements\n- Python" and "Responsibilities\nGo\nrequired\nBuild things daily" return `must` because `_heading_above` falls back to `classify(lines[index])` when the joined pair is not a heading (eval_headings.py:89).
**Suggested fix:** Treat a list item whose text is exactly a known heading phrase (after the bullet is removed) as a heading, and when a wrapped pair joins into a recognised non-heading phrase or a denial, return None instead of falling back to the second line. Add tests for each probe.
**Resolution:** Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording. Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..e163dd9): `eval_headings.py` is absent from engine/src/engine/jobs, `rg 'eval_headings|classify|marker|importance_source'` finds nothing in engine/src or tests, `eval_extract.verify` reads no text around the quote, and nothing worse replaced it (engine 714 passed, ruff and mypy clean).

### stop-reading-importance-from-the-posting/F-167 [P3] closed - Common real headings and bullet styles are not recognised, so a normal posting often states nothing

**File:** engine/src/engine/jobs/eval_headings.py:29
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, tests)
**Why it matters:** Only exact phrases count. Probed `classify` (all give None or `other`, so importance falls back to the model's guess capped at `important`, which only lowers): `Minimum requirements`, `Job requirements`, `Technical requirements`, `Skills required`, `Who you are`, `What we're looking for`, `Qualifications` (other), `Requirements (must-have)`, `Nice to have skills`, `Plus points`, and the curly apostrophe `What you\u2019ll need` (fold does not normalise it; scraped postings use it constantly). En and em dash bullets are not items, so "Requirements\n- A\n\u2013 B\n\u2013 Rust" gives None for B, and a wrapped bullet continuation line ends the run (the `Go` after "- Python and\n  Rust" gives None). Safe direction, but a real reduction in how often `stated` is available; no test measures it.
**Suggested fix:** Add the common phrases (`minimum requirements`, `job requirements`, `technical requirements`, `who you are`, `what we're looking for`, `plus points`, `... skills`), normalise `\u2019` to `'` in `_text`, and accept `\u2013` and `\u2014` as bullets. Add tests.
**Resolution:** Superseded 2026-11-11 (fix `stop-reading-importance-from-the-posting`, the user's decision after the fifth review round): the code this finding is about is deleted. `eval_headings.py` and the wording and heading readers are gone; importance is the model's own guess, capped at `important`, and nothing claims that the posting states it (prompt `eval-extract-3`). No test or source reads headings, labels or importance wording. Closed 2026-11-11 by independent review (fresh subagent, delta 55b6e4d..e163dd9): `eval_headings.py` is absent from engine/src/engine/jobs, `rg 'eval_headings|classify|marker|importance_source'` finds nothing in engine/src or tests, `eval_extract.verify` reads no text around the quote, and nothing worse replaced it (engine 714 passed, ruff and mypy clean).

## Independent review

**Status:** passed
**Target commit:** e163dd953fa4500ce729980d8651f15e87c3375b
**Base commit:** 55b6e4def3127c6c51a96549910d6da5db60f56e
**Base ref:** main
**Spec hash:** a1a411392c0bf20047821a85f4eaeb2fdf48396f033628c8a7475fba910f5d17
**Prepared by:** claude
**Builder model:** claude-fable-5-2
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T09:58:19Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T10:02:02Z
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
- `git diff 55b6e4d..e163dd9` (engine/src, web/src, tests): reviewed in full
- `cd engine && uv run --env-file ../.env pytest -q`: pass (714 passed, 10 skipped)
- `cd engine && uv run ruff check .`: pass
- `cd engine && uv run mypy`: pass (108 files)
- `cd web && npm run lint && npm run typecheck && npm test`: pass (exit 0)
- scratch probe of `RequirementOut.model_validate` with a legacy row (`importance_source`, `must`): validates, extra key dropped, `must` kept

## Evidence

- `eval_headings.py` and its tests are gone; `rg` finds no `eval_headings`, `classify`, `marker` or `importance_source` in engine src or tests; `is_negated` removed, `_NEGATION` still used in gates.py.
- `eval_extract.verify` locates the quote with `quotes.locate`, caps `must` to `important`; the prompt asks only for `important` or `nice`; the prompt version is in `_cache_key`; owner scoping and the no-logging test are unchanged; no migration touched.
- Tests keep the quote rule, one-field rule, wrapped lines, pay formats, cents rule and 60-item cut.
- F-163 to F-167 closed: the code they describe no longer exists.

## Findings

- F-168 [P2] open: docs and build plan still say importance is read from the posting first
- F-169 [P3] open: stale must-have comments, unreachable must branches, homepage example
- F-170 [P3] open: pre-change evaluation rows still served as `must` and current
- F-163, F-164, F-165, F-166, F-167 closed

## Remaining risk

- No P0 or P1 is open. F-168 to F-170 are non-blocking.
- No live model run: whether the cheap model's `important` or `nice` guess is good is untested (8d's golden set).
- Web test output was seen only as a successful exit, not a count.
