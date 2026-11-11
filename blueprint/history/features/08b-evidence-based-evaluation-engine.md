# Feature: Evidence-based evaluation (engine)

**From build-plan:** feature 8b
**Build attempt:** 1
**Status:** verified
**Branch:** feature/evidence-based-evaluation-engine

## Goal

For one saved job and one track the user picks, produce an evaluation they can check: the
posting's requirements with how important each is, whether each is met by the user's own
**confirmed or edited** profile facts (with the facts cited) or honestly unknown, the main
gap, a few practical checks, and a fit band decided by code. Nothing here is a percentage
and nothing is claimed that a cited fact does not support. This feature adds engine and
web API only; the Fit step screen is feature 8c.

## Decisions already made (2026-11-11)

- **Band by code from must-haves.** The model judges each requirement; fixed code turns
  those judgements into the band. Bands: Strong, Good, Stretch, Weak fit (stored `poor`).
- **Budget is a hard cap on model work, no web research** (company research is feature 14):
  one cheap-tier extraction and one strong-tier evidence call per evaluation, the posting
  cut to 12,000 characters, at most 20 requirements, a bounded list of profile facts.
  Identical input is a cache hit and makes no call. (The gateway's own single retry on an
  unusable JSON reply is the only extra call.)
- **The user picks the track** for each evaluation. 8c defaults the choice to the first
  track whose gates and screen passed.
- The salary floor is **monthly**. The band label for a poor fit is **Weak fit**.

## In scope

1. **Table `engine.evaluation`**, one row per job and track (replaced when re-run): `id`,
   `user_id`, `job_id` (cascade), `track_id` (cascade), `profile_id` (cascade) and
   `profile_version`, `rules_key` (the track rules fingerprint from `screening.rules_key`),
   `cache_key` (content hash, see Data), `band` (`strong`, `good`, `stretch`, `poor`),
   `summary`, `main_gap` (json, null), `requirements` (json), `checks` (json),
   `usage_event_ids` (json list), `created_at`, `updated_at`. Unique on `job_id` and
   `track_id`. Alembic migration `0011`.
2. **Band, main gap, summary and checks in code** (`engine/jobs/eval_band.py`, pure):
   - Core requirements are the must-haves; when the posting states none, the important ones.
   - `bad` = core requirements with status `gap` or `unknown`. Band: `poor` when `bad` is 2
     or more, or gaps are more than half of the core; else `stretch` when `bad` is 1; else
     `good` when any core requirement is `partial` or (core are must-haves and an important
     requirement is a `gap`); else `strong`. No requirements at all is an error, not a band.
   - Main gap: the first core requirement that is a `gap`, else the first `unknown`, else null.
   - Summary: one sentence built by code, for example "6 of 7 must-haves have evidence".
   - Checks, information only (they never change the band): **salary** (posting pay, monthly
     equivalent, against the track's monthly floor, only when the currencies match and the
     period is month or year; otherwise `unknown`), **work mode** (what the posting states
     against the track's modes: `matches`, `differs`, `unclear`) and **region** (a region
     restriction against the track's eligibility notes: `none_found`, `compatible`, `mismatch`, `unclear`).
     Work mode and region reuse the detection in `gates.py` through two small public helpers.
3. **Requirement extraction** (`engine/jobs/eval_extract.py`): a `cheap`-tier task that
   returns requirements (`need`, `importance`, `quote`, `marker`) and the posting's stated
   pay (`min`, `max`, `currency`, `period`, `quote`) or null. Code verifies every quote, every pay figure (it must appear in its quote) and
   marker is really in the title, company, location or description. A requirement without a
   real quote is dropped. **Importance is read from the posting first:** it counts as
   stated only when the model gives a `marker` that is whole words of the posting ending
   before the quote, names an importance in code's word lists (must-have wording gives
   `must`, nice-to-have wording gives `nice`) and agrees with the nearest importance wording
   above the quote; the importance is then set by those words, not by the model's claim.
   Otherwise it is inferred, and an inferred importance is **capped at `important`**.
4. **Evidence** (`engine/jobs/eval_evidence.py`): the user's confirmed or edited facts
   (experiences with their bullets, skills, achievements, projects, education), numbered
   with short labels, and a `strong`-tier task that returns for each requirement a status
   (`met`, `partial`, `gap`, `unknown`), the labels of the facts that support it (at most 5)
   and a one-sentence note. Code maps labels back to real facts and **downgrades** `met` or
   `partial` with no valid label to `unknown`. Unconfirmed (`extracted`) facts are never sent
   and never cited.
5. **Service** (`engine/jobs/evaluating.py`): `evaluate_job(user_id, job_id, track_id)` and
   `list_evaluations(user_id, job_id)`; owner scoping on the job, the track and the profile;
   a cache hit when the `cache_key` is unchanged; all-or-nothing save (a failure keeps the
   previous result and saves nothing new); a `stale` flag when the profile version, the
   profile or the track rules changed since.
6. **Engine routes** `POST /internal/jobs/{id}/evaluate` (body `{"trackId": "<uuid>"}`) and
   `GET /internal/jobs/{id}/evaluations`, and **web routes** `POST /api/jobs/$id/evaluate`,
   `GET /api/jobs/$id/evaluations` with client functions and types in `web/src/lib/jobs-api.ts`.
7. **Tests** for every item above (see Testing).

## Out of scope

- Any screen or UI: the Fit step (8c), Today and the Jobs list (9, 7), Filtered out (10).
- The golden set and `uv run eval` (8d). Band thresholds here are the starting rule; 8d
  tunes them against the founder's own verdicts.
- Web or company research (14), tailored documents (11), seniority checks, opportunity
  types (34), stages (12), cost reporting (35).
- Automatic evaluation after adding a job or on a schedule (the trigger is 8c and 10).
- Calling the gates or the screen from here: an evaluation does not require either to have
  run, and does not change their results.
- Any new dependency, service or configuration setting. Models come from the existing tier
  settings in `.env`, which the user edits; no key is read or printed here.

## Build loop

`workflow.stepReview` is `feature` and `workflow.checkpointCommits` is `disabled`. The
Continuous run builds all steps, runs Verify once, obtains the independent review the
config requires for a migration and user data, and completes locally.

## Build steps

- [x] 1. Migration `0011_evaluation.py`, the `Evaluation` model in `engine/src/engine/models.py`
  and `engine/tests/test_evaluation_table.py`; `tests/test_db.py` expects table `evaluation`
  and head `0011`.
  **Done when:** the table tests pass: defaults, the band check, the unique pair, cascade from
  job, track and profile, and a row needing a real job, track and profile.
- [x] 2. `engine/src/engine/jobs/eval_band.py` (band, main gap, summary, salary, work mode and
  region checks), plus the two public helpers in `gates.py`; `engine/tests/test_eval_band.py`.
  **Done when:** the tests pass, covering every band including the boundaries (one bad
  must-have, two, more than half gaps, only partials, an important gap, no must-haves so the
  important ones are core, no requirements), the main gap order, the salary check (monthly,
  yearly, other currency, no period, no floor, only a minimum) and the work mode and region
  checks, and `gates.py` behaviour is unchanged (its tests still pass).
- [x] 3. `engine/src/engine/jobs/eval_extract.py` and `engine/tests/test_eval_extract.py` with the
  fake provider of `test_ai_gateway.py`.
  **Done when:** the tests pass: a real quote and marker give a stated importance; a marker
  that is not in the posting, or comes after the quote, gives an inferred and capped
  importance; a requirement without a real quote is dropped; at most 20 are kept; pay is kept
  only with a real quote; the posting is sent as delimited data and a closing tag inside it
  is neutralised; an unusable reply twice is an error; nothing is logged.
- [x] 4. `engine/src/engine/jobs/eval_evidence.py` and `engine/tests/test_eval_evidence.py`.
  **Done when:** the tests pass: only `confirmed` and `edited` facts are rendered; labels are
  unique and stable for the same profile; a cited label that is not in the list is dropped; a
  `met` with no valid label becomes `unknown`; more than 5 labels are cut to 5; the fact list
  is bounded (400 facts, 30,000 characters) in a stated order; a reply that omits a
  requirement leaves it `unknown`.
- [x] 5. `engine/src/engine/jobs/evaluating.py` and `engine/tests/test_evaluating.py` against
  the test database.
  **Done when:** the tests pass: a full run with fakes saves one row and returns the requirements,
  band and checks; a second identical run makes no model call; a changed profile version or
  track rule gives a new run and the old row is replaced; `stale` shows after a profile edit;
  no confirmed facts gives `no_confirmed_profile` (409) before any call; no requirements gives
  `no_requirements` (422); a failing or unconfigured model saves nothing and keeps the previous
  row; another user's job, track and profile are never read or written; a job or track deleted
  mid-run gives `not_found`; no posting, fact or quote text reaches logs.
- [x] 6. The two engine routes in `engine/src/engine/jobs/routes.py` and
  `engine/tests/test_evaluation_routes.py` (using only runs that need no model, such as the
  error paths and a pre-saved row).
  **Done when:** the tests pass for success, `not_found` for a made-up or foreign job or track,
  `validation_failed` for a missing or malformed `trackId`, `no_confirmed_profile`, and the
  stable error body.
- [x] 7. Web: handlers in `web/src/server/jobs/http.ts`, routes `web/src/routes/api/jobs/$id/evaluate.ts`
  and `evaluations.ts`, types and client functions in `web/src/lib/jobs-api.ts`, and tests
  in `jobs-http.test.ts`, `jobs-api.test.ts` and `jobs-routes.test.ts`.
  **Done when:** the web tests pass and show the handlers forward only to the two engine paths
  with the session user, refuse a bad id before the engine, refuse an oversized body, pass the
  engine's errors through, and the route tree contains both paths.

## Files / areas

- New: `engine/migrations/versions/0011_evaluation.py`, `engine/src/engine/jobs/eval_band.py`,
  `eval_extract.py`, `eval_evidence.py`, `evaluating.py`; web `api/jobs/$id/evaluate.ts` and
  `evaluations.ts`; the tests named in the steps.
- Changed: `engine/src/engine/models.py`, `engine/src/engine/jobs/gates.py` (two public
  helpers, no behaviour change), `engine/src/engine/jobs/routes.py`,
  `web/src/server/jobs/http.ts`, `web/src/lib/jobs-api.ts`, `web/src/routeTree.gen.ts`
  (generated), `engine/tests/test_db.py`.
- Not touched: the web screens, the `job`, `job_screen`, profile and track tables, billing.

## Data / contracts

Every statement filters on `user_id`; the job, the track and the profile must all belong to
that user. The profile used is the user's latest parsed one (`latest_profile`).

`cache_key` is the SHA-256 (first 32 hex characters) of the canonical JSON of: the job's
title, company, location and description; `profile_id` and `profile_version`; the track's
`rules_key` and its `criteria`; and the two prompt versions. It is the content hash the plan
asks for. The gateway cache also applies to each task on its own.

`requirements` (json list, at most 20): `need` (text, at most 200 characters), `importance`
(`must`, `important`, `nice`), `importanceSource` (`posting`, `inferred`), `quote` (verbatim
from the posting, 6 to 200 characters), `status` (`met`, `partial`, `gap`, `unknown`),
`evidence` (list of up to 5 `{kind, id, text}`, each a real confirmed or edited fact of the
profile, `text` a short rendering of it), `note` (one sentence, at most 200 characters).

`checks` (json): `salary` `{status: meets|below|unknown, postingMonthly: number|null,
floorMonthly: number|null, currency: text|null, quote: text|null}`; `workMode`
`{status: matches|differs|unclear, posting: text|null}`; `region`
`{status: none_found|compatible|mismatch|unclear, region: text|null}`.

`EvaluationOut` (camelCase): `id`, `jobId`, `trackId`, `trackName`, `profileVersion`, `stale`,
`band`, `summary`, `mainGap` (`{need, status, note}` or null), `requirements`, `checks`,
`updatedAt`. Errors keep the existing shape: `not_found` (404), `validation_failed` (422),
`no_confirmed_profile` (409, "Confirm some of your profile first."), `no_requirements` (422,
"We could not find requirements in this posting."), and the gateway's `ai_not_configured`
(503), `ai_unavailable` (502) and `ai_output_invalid` (502).

Tasks: `eval-extract` (workflow `evaluate`, tier `cheap`, prompt `eval-extract-1`) and
`eval-evidence` (workflow `evaluate`, tier `strong`, prompt `eval-evidence-1`). A prompt
version changes whenever its text does and is part of the cache key. The posting is
untrusted: it is delimited data, and nothing it says can change a status or a band, because
quotes and labels are verified in code and the band is computed in code. The user's facts are
also sent as delimited data. Posting text, facts, quotes and notes are never logged and
never written to the usage ledger.

## Testing

- Baseline observed this session on `main` at `c880dd7`: web lint, typecheck and build passed;
  web tests 203 passed, 1 skipped; engine ruff, format check and mypy passed; engine tests
  545 passed, 9 skipped.
- New engine tests per step with the fake provider; one live test, skipped when no model key
  is configured, following `test_cv_parse_live.py`.
- The final Verify command from `AGENTS.md` must pass. No browser evidence: no screen.

## Notes for the AI

- Honest results: a status needs cited facts or it is `unknown`; never fill a gap. No
  percentage anywhere. AI output is labelled when shown (8c).
- Conservative direction: a doubt becomes `unknown`, which shows as an honest gap, never as a
  match.
- Prefer the standard library and the existing gateway; no new dependency.
- Never print or ask for secret values; the user edits `.env`.
- Known and accepted: two simultaneous evaluations of the same job and track can both run;
  the second finds the first's row only after it saves. A cache hit makes a repeat free.
- Open findings F-138, F-140 to F-143 from 8a are not part of this feature; do not widen into
  them.

## Open questions

None blocking. The band thresholds are the starting rule and are expected to change after the
golden set (8d).

## Step notes

**Built (2026-11-11):** migration `0011_evaluation.py` and the `Evaluation` model; `jobs/eval_band.py` (band, main gap, summary, salary, work mode and region checks); two public helpers in `jobs/gates.py` (`stated_work_mode`, `region_status`; gate behaviour unchanged); `jobs/eval_extract.py` (cheap task `eval-extract-1`, quote and marker verification, capped inferred importance, pay); `jobs/eval_evidence.py` (confirmed and edited facts only, labels, task `eval-evidence-1`, label verification and downgrade); `jobs/evaluating.py` (`evaluate_job`, `list_evaluations`); engine routes; web handlers, routes, client types and `bandLabel`; tests per step and one live test skipped without `AI_LIVE_TEST=1`.

**Decisions made while building**

- The region check has four statuses: `none_found`, `compatible` (a limit the track's notes or locations mention), `mismatch`, `unclear` (a limit, but no eligibility notes). `compatible` was added to the first draft.
- The gateway caches each task by its own input, so a profile version change with the same facts, or a track rule change the model never reads, recomputes the band and checks from cached model answers without a model call. The saved row is still replaced and no longer stale.
- When the requirements and the facts are both unchanged, nothing is sent at all (the evaluation `cache_key` matches).
- A band with no must-haves or important requirements uses all requirements as the deciding set.

**Repair round 1 (after the independent review requested changes):** F-144 (P1) importance now comes from the marker's words, F-145 the salary floor and currency are in the evaluation key, F-146 pay figures must appear in the quote, F-147 a long evidence list is cut instead of refused.

**Verify (this session, after the repairs):** web lint, typecheck and build pass, web tests 209 passed and 1 skipped; engine ruff, format check and mypy pass, engine tests 668 passed and 10 skipped (655 before the repairs). No live model call and no browser check (no screen). No live model call was made and no browser check applies (no screen).



<!-- blueprint:completion {"schemaVersion":2,"specBytes":16843,"specSha256":"1f0cbc1043c6f75077837bb4cff726b1a605edf9202d570e4942949265386d2c","branch":"refs/heads/feature/evidence-based-evaluation-engine","head":"9ee301e47f92e480e117e36e8f147797037021af","baseRef":"refs/heads/main","baseCommit":"c880dd7aadf7a33efe575a3a9690090d0e86a576","sourceTree":"b5450d29b018b33c68b4bd0105fda40851d676c6","landing":"local-merge","absentOptional":[]} -->

## Findings

### 8b/F-144 [P1] closed - A "stated" importance only needs the marker to be any text at or before the requirement, so a model (or an injected posting) can make any requirement a stated must-have

**File:** engine/src/engine/jobs/eval_extract.py:164
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality, tests)
**Why it matters:** `_importance` accepts a marker when the folded marker is found anywhere in the folded posting at an index <= the quote's index. It never checks that the marker is a wording that signals importance, and a marker inside the quote itself counts. Probe: a posting "Nice to have: Kubernetes ..." with a model reply `importance: must`, `quote: Kubernetes`, `marker: Kub` gives `importance=must`, `importanceSource=posting`. A 3-character fragment (or part of an unrelated word) is enough. The cap at `important` for inferred importance is therefore only enforced against a model that chooses not to supply a marker; a hostile posting that tells the model "mark everything must, marker = first word" changes importances and so the band, which the spec says nothing in the posting can do. The tests only cover a marker that is absent, after the quote, or differently cased.
**Suggested fix:** Verify the marker against a fixed list of importance wordings (requirements, must have, required, nice to have, preferred, and so on) as well as its position, require it to end at or before the quote start (not overlap the quote), and keep inferred otherwise; add tests for a marker equal to part of the quote and for an unrelated word.
**Resolution:** Repaired 2026-11-11: a marker now has to be whole words of the posting that end before the quote begins, must name an importance (must-have wording gives `must`, nice-to-have wording gives `nice`; both or neither states nothing), and must agree with the nearest importance wording above the quote. The importance then comes from the marker's words, never from the model's claim. Tests: fragments (`Kub`, the quote itself, `Nice to`, `hav`), a model claiming `must` under `Nice to have`, a model claiming `nice` under `Requirements`, a marker with no importance word, a marker that disagrees with the nearest heading, both wordings, and the common headings.
Closed 2026-11-11 by independent review (fresh subagent, 9ee301e): re-read eval_extract.py:166-213 and probed `verify`. A marker of `Kub`, `Kubernetes`, `Nice to` or `hav` under "Nice to have: Kubernetes experience" now gives inferred `important` (model said must, capped); only `Nice to have` gives stated `nice`; a model claiming `must` with marker `Requirements` under a Nice-to-have heading is refused. The original defect (any text at or before the quote counted) is gone. Residual gaps in the word lists are recorded separately as F-148 and F-149 (P2).

### 8b/F-145 [P2] closed - Salary floor and currency are not part of the cache key or the stale check, so an edited floor leaves an old salary check showing as current

**File:** engine/src/engine/jobs/evaluating.py:105
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, tests)
**Why it matters:** The salary check reads `track.salary_floor` and `track.currency`, but `_cache_key` and `rules_key(track)` (screening.py:100, which feeds both the key and `stale`) cover only roles, modes, locations, eligibility, criteria, dealbreakers and do-not-apply. After the user changes the floor or currency, `evaluate_job` returns the saved row as a cache hit with the old `floorMonthly` and a `meets`/`below` result, and `stale` stays false. The spec says a result is stale when the track rules changed and the cache key follows the content the result depends on. No test changes the floor.
**Suggested fix:** Add `salary_floor` and `currency` to the evaluation's own cache key and staleness comparison (without changing `rules_key` for the screen unless that is wanted), and add a test that editing the floor recomputes the check without a model call.
**Resolution:** Repaired 2026-11-11: `evaluation_rules_key` (the screen's rules plus the salary floor and currency) is used for the cache key, the stored `rules_key` and `stale`. Tests: a floor edit and a currency edit each show stale, are recomputed without a model call, and give `below` and `unknown`.
Closed 2026-11-11 by independent review (fresh subagent, 9ee301e): `evaluation_rules_key` (evaluating.py:105) adds `salary_floor` and `currency` to `rules_key(track)` and feeds the cache key (line 122), the saved `rules_key` (247) and `stale` (87); `test_an_edit_to_the_salary_floor_or_currency_is_not_served_from_the_old_row` passes. Key order is stable (`sort_keys`).

### 8b/F-146 [P3] closed - Posting pay numbers are not checked against the quote, so a salary verdict can rest on invented figures

**File:** engine/src/engine/jobs/eval_extract.py:174
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, quality)
**Why it matters:** `_pay` keeps the pay when its quote (4 characters or more, an odd `MIN_QUOTE_CHARS - 2`) appears anywhere in the posting; `min`, `max`, currency and period are never required to appear in the quote. The salary check can therefore say `meets` or `below` with numbers the posting does not contain. It is information only and does not change the band, but the feature's rule is that nothing is claimed that the posting does not support.
**Suggested fix:** Require each stated number (after removing separators and a `k` suffix) to appear in the quote, and use the same minimum quote length as requirements.
**Resolution:** Repaired 2026-11-11: each pay figure the model reports must appear in its quote (3,000, 80k and 3.5k are read), otherwise the pay is dropped. Tests: invented figures, one invented figure, a digit fragment, and k and decimal forms.
Closed 2026-11-11 by independent review (fresh subagent, 9ee301e): `_pay` (eval_extract.py:234) requires every figure to be among `_amounts(quote)`; probes: `$13,000` with min 3000 dropped, `3.5k` read, invented figure dropped. A narrower problem with shared-suffix ranges (`3-4k`) is recorded as F-150.

### 8b/F-147 [P3] closed - More than 20 cited labels fails the whole evidence reply instead of being cut to 5; unused constant left in eval_band

**File:** engine/src/engine/jobs/eval_evidence.py:139
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, tests)
**Why it matters:** `Judgement.evidence` has `max_length=20`, so one over-long list makes the reply invalid (a retry, then `ai_output_invalid`), although the spec says labels over 5 are cut to 5 and the tests cover only 6. Separately `HOURS_NOT_COMPARED` in eval_band.py:15 is defined and never used (dead code).
**Suggested fix:** Drop the field cap and slice to the first 5 in `verify` (or accept a longer list and truncate in a validator); delete the unused constant.
**Resolution:** Repaired 2026-11-11: a long evidence list is cut to its first 20 labels before validation, and verification keeps at most 5, instead of refusing the reply; the unused `HOURS_NOT_COMPARED` constant is removed. Test: 39 labels give 5 cited facts.
Closed 2026-11-11 by independent review (fresh subagent, 9ee301e): probe with 39 cited labels gives 5 cited facts and no refusal (eval_evidence.py:40, 259); `HOURS_NOT_COMPARED` is gone from eval_band.py. The same refuse-instead-of-cut pattern still exists on the 60-item caps, recorded as F-151.

## Independent review

**Status:** passed
**Target commit:** 9ee301e47f92e480e117e36e8f147797037021af
**Base commit:** c880dd7aadf7a33efe575a3a9690090d0e86a576
**Base ref:** main
**Spec hash:** 1f0cbc1043c6f75077837bb4cff726b1a605edf9202d570e4942949265386d2c
**Prepared by:** claude
**Builder model:** claude-fable-5-2
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T08:38:21Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T08:46:00Z
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
- `cd engine && uv run --env-file ../.env pytest -q`: pass (668 passed, 10 skipped)
- `cd engine && uv run ruff check .`: pass
- `cd engine && uv run mypy`: pass (106 source files)
- `cd web && npm run lint && npm run typecheck && npm test`: pass (209 passed, 1 skipped)
- Scratch probes outside the repo (`/tmp/rev8b/probe*.py`) against `eval_extract.verify` and `_pay`: run, no live model call (AI_LIVE_TEST not set)
- `/check`: not run (Check required: no)

## Evidence

- Reviewed the full `c880dd7..9ee301e` delta (migration 0011, model, eval_band, eval_extract, eval_evidence, evaluating, gates helpers, engine and web routes, handlers, types, tests) across quality, security, performance and tests.
- Owner scoping: every fact, job, track and profile query filters on user_id; facts are limited to confirmed and edited rows; the gateway cache is per user; logs and the retry reason carry field paths only.
- Band rule matches the spec (boundaries, important-gap case, main gap order); cache key and `stale` now include the salary floor and currency; replacement uses one upsert, failures keep the old row, foreign-key errors map to not_found.
- Probes show the marker fragments (`Kub`, quote text, `Nice to`) are refused, but negated wording and unrecognised headings still state a must (F-148, F-149); pay and quote edge cases in F-150 to F-152; regex cost on a 12,000-character posting with 40 requirements is about 10 ms.
- Earlier entries F-144 to F-147 re-examined against the code and closed.

## Findings

- New: F-148 [P2], F-149 [P2], F-150 [P3], F-151 [P3], F-152 [P3], F-153 [P3] (all open)
- Closed after re-examination: F-144, F-145, F-146, F-147
- F-138 and F-140 to F-143 are out of scope and unchanged

## Remaining risk

- The importance rule can still overstate `must` for negated wording or under headings outside its word lists (F-148, F-149); a hostile posting can also legitimately state importance with its own "Requirements" heading, which the design accepts.
- Concurrent evaluations of one job and track may both call the model and the later save wins (accepted in the spec).
- No live model call and no browser check were made; model behaviour with the real prompts is untested.
