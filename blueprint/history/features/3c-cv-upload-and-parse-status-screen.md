# Feature: CV upload and parse status screen

**From build-plan:** feature 3c
**Build attempt:** 1
**Branch:** feature/cv-upload-and-parse-status-screen
**Status:** verified

## Goal

A signed-in user can upload a CV, ask for it to be read into a profile draft, watch the real
status, recover from every failure the engine can report, see what was found, and delete the
CV, all on `/onboarding` (step 1 of the design's four-step flow). It uses only routes that
exist (`/api/cv`, `/api/cv/:id`, `/parse`, `/profile`, `DELETE`) and tells the truth about
what is built: the draft can be seen but not yet reviewed or confirmed (feature 4).

## Design reference

Approved canvas `https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q`: the **Onboarding** board
(step 1, upload and parse progress) and the **States** board (error: "CV could not be read",
loading skeletons, error card style). The board sources were read from the canvas file
`project/Onboarding.dc.html` and `project/States.dc.html`; copy them to
`blueprint/reference/onboarding.dc.html` and `states.dc.html` in step 2 so the check does not
depend on the canvas being reachable.

Required match: Fredoka headings and Nunito body from the existing tokens, Migo with a speech
bubble ("Hi, I'm Migo. Drop in your CV and I'll do the boring bit."), the four-pill stepper
(Upload CV active, the others upcoming), the white rounded card, the dashed dropzone with an
upload icon, "Choose a file" pill button, the file card with status label, progress bar and
check/half-circle step list, the three-line trust box with icons, pill buttons (primary
`#B04A27`), 44px touch targets, reduced-motion support.

Deviations, each stated in the final packet (honest copy or unbuilt backend):
1. Size limit reads "up to 5 MB" (the engine limit), not 10 MB.
2. The progress bar is indeterminate while parsing; no percentage is shown (none exists).
3. The right-hand "What are you looking for?" tracks card is not built (feature 5); it is
   replaced by nothing on desktop (single centred card, same widths as the board's left card).
4. "Review my profile" is not a link (feature 4 is unbuilt): the success view shows what was
   found and says profile review comes next.
5. "Never sold" and "Delete it any time in settings" are not claimed: the trust box states what
   is true today (private storage, text sent to DeepSeek only when the user presses the build
   button, a Delete button on this page).
6. "No CV handy? Add your details by hand" is omitted (no manual entry yet).
7. The page is inside the app shell (sidebar), as every signed-in page is; the board shows the
   bare onboarding canvas.

## In scope

1. A small typed client for the CV routes (`web/src/lib/cv-api.ts`) with stable result shapes,
   and a pure view-model module (`web/src/lib/cv-view.ts`): file validation (PDF or DOCX by
   extension and MIME, 5 MiB), mapping of a CV row to a screen state, mapping of every
   upload and parse error code to calm, specific copy and the available actions.
2. The `/onboarding` route under `_app` with these states: no CV (dropzone), uploading,
   uploaded and ready ("Build my profile draft" button beside the AI disclosure), parsing
   (polling), parsed (counts of roles, skills, achievements, projects, education and the
   headline, labelled as unconfirmed), failed (message and the right action per code), upload
   errors, and delete with an inline confirm. A returning user sees their latest CV's state.
3. Entry points: a card on `/dashboard` linking to `/onboarding`, and the sign-up success
   redirect going to `/onboarding` (sign-in still goes to `/dashboard`).
4. The design check evidence and copies of the two board sources in `blueprint/reference/`.

## Out of scope

- Reviewing, editing or confirming facts, tracks and criteria (4, 5), the stepper's later
  steps, a manual-entry path, drag-to-reorder or multiple CVs (the latest CV is shown),
  settings, export, account deletion, push or email notifications about the parse.
- Any engine or API change. Raising the 5 MiB limit or showing real progress percentages.
- Browser test harness (none is configured); evidence is a scripted headless capture.

## Build loop

`blueprint/config.json`: `stepReview: feature`, `checkpointCommits: disabled`; this run is
Continuous Mode, so there are no review pauses. Independent review is required
(`when-sensitive`: it uploads and deletes personal data), through an approved-by-run immutable
checkpoint and the automatic isolated reviewer.

## Build steps

- [x] 1. **Client and view model.** `web/src/lib/cv-api.ts`: `uploadCv(file)` (raw bytes,
  `X-Filename` percent-encoded, filename never logged), `listCvs()`, `getCv(id)`,
  `startParse(id)`, `getDraft(id)`, `deleteCv(id)`; each returns `{ ok: true, data }` or
  `{ ok: false, code, message }` and never throws on an HTTP error; `fetchFn` is injectable.
  `web/src/lib/cv-view.ts`: `validateFile`, `screenFor(cv)`, `copyFor(code)`, `summarise(draft)`,
  `shouldKeepPolling(startedAt, now)`. Done when Vitest cases pass for: file type and size
  checks (PDF, DOCX, other types, 0 bytes, exactly 5 MiB and one byte over); every parse error
  code and every upload error code mapping to copy with no raw message or code shown;
  `screenFor` for each status including `failed` with each code; the upload request carrying
  the encoded name and the bytes as the body; a non-JSON or network failure becoming a stable
  error; polling stopping after a terminal state or after 3 minutes (`npm test`).
- [x] 2. **The page.** `web/src/routes/_app/onboarding.tsx` (and a small
  `web/src/components/cv/` set if the file grows past about 300 lines): all states in
  In scope item 2; TanStack Query with `refetchInterval` 2 s only while `parsing`; focus and
  announcements (`role="status"` for progress, `role="alert"` for failures, the file input
  labelled, the dropzone keyboard-operable, errors cleared on the next attempt); reduced
  motion via the existing classes; Migo from `components/Migo.tsx`; regenerate
  `routeTree.gen.ts`; the dashboard card and the sign-up redirect; copy the two board sources
  to `blueprint/reference/`. Done when `npm run build` and typecheck pass, `/onboarding` loads
  signed in (and redirects to `/sign-in` signed out), and a real upload of a PDF and a DOCX
  against the local engine and storage reaches the uploaded-and-ready state.
- [x] 3. **Design check, evidence and docs.** With the local engine, storage and database
  running and a throwaway local test account, capture the screen at 1440 and 390 wide for:
  no CV, uploaded and ready, parsing, failed (no AI configured), failed (unreadable file), and
  parsed (a draft inserted directly into the local dev database as test data) beside the
  Onboarding and States boards; list each difference; check the console and network for
  errors; update `docs/technical-design.md` and the README status row. Done when each state
  was seen in the browser, the differences list matches the Deviations above (any other
  difference is fixed), the console shows no errors, and the full Verify command passes.

- [x] 4. **Repair the review's findings F-75 to F-80 (and the 401 part of F-81).** A way out of the
  parsing view (delete with confirm, also after the poll limit); focus handling in the delete
  confirm and after upload and delete, and a live region on the upload status; one alert in the
  failed view; no retry for `ai_not_configured`; honest intro and dashboard copy; a full-width
  dimmed bar under reduced motion; any 401 goes back to sign-in. Done when lint, typecheck and the
  updated unit cases pass, and the browser shows the delete control while parsing, focus moving
  to "Keep it" and back, one alert after a failed retry, and focus on the heading after a delete.

## Files / areas

`web/src/lib/cv-api.ts`, `web/src/lib/cv-view.ts`, `web/src/routes/_app/onboarding.tsx`,
`web/src/components/cv/*`, `web/src/routes/_app/dashboard.tsx`, `web/src/components/AuthForm.tsx`,
`web/src/routeTree.gen.ts`, `web/tests/cv-view.test.ts`, `web/tests/cv-api.test.ts`,
`blueprint/reference/{onboarding,states}.dc.html`, `docs/technical-design.md`, `README.md`.

## Data / contracts

Consumes the existing responses: CV `{id, filename, mime, sizeBytes, parseStatus, parseError,
createdAt}`; list `{items}` newest first; draft `{id, cvId, headline, summary, experiences[],
skills[], achievements[], projects[], education[]}` (each row has `status`); errors
`{code, message}` with codes `cv_too_large`, `cv_unsupported_type`, `cv_unreadable`,
`unauthorized`, `not_found`, `engine_unavailable`, and parse codes `ai_not_configured`,
`ai_unavailable`, `ai_output_invalid`, `ai_input_invalid`, `text_too_long`,
`no_profile_found`, `interrupted`, `internal`.

Screen states: `empty`, `uploading`, `ready` (status `extracted`), `parsing`, `parsed`, `failed`.
Actions per failure: retryable (`ai_not_configured`, `ai_unavailable`, `ai_output_invalid`,
`ai_input_invalid`, `interrupted`, `internal`) show "Try again" (`POST /parse`) and "Upload
another file"; `text_too_long` and `no_profile_found` show only "Upload another file", which
deletes the failed CV first (one CV at a time) after the user chooses it. The browser never
shows a raw engine message or code. All user text (the filename, the headline, bullets) is
rendered as React text, never as HTML.

Trust and tenancy: nothing new server-side; every call goes through the existing session-checked
routes, and the page never builds a CV id from anything but a server response.

## Testing

Vitest for the two lib modules (no DOM library is installed and none is added). The page is
checked in a real browser (headless Chrome through the DevTools protocol) as step 3 describes;
screenshots are evidence only and are not committed except the ones used in the README.

## Notes for the AI

- Follow `AuthForm.tsx` and `dashboard.tsx` for patterns, `styles.css` tokens for colour.
- Honest copy rules apply (see the Deviations); say "unconfirmed" for found facts.
- Do not add a dependency. Use `fetch` and TanStack Query, which are installed.
- If the live parse cannot run (no model or key in `.env`), the parsed state is shown with a
  directly inserted test draft and that is stated in the evidence; never claim a live parse.

## Open questions

None blocking. (The DeepSeek model id and key are still unset; they affect only a live parse.)

## Evidence (recorded during the build)

Repair pass (step 4): the delete control while parsing, focus moving to "Keep it" and back to "Delete this CV", one alert in the failed view after a failed retry, focus on the heading after a delete, and no console errors were seen in the browser. The leftover test CV rows and objects from the first pass were removed.

- Browser pass (headless Chrome, local web, engine and storage, a throwaway local test account,
  1440 and 390 wide) saw: empty; wrong file type refused in the browser; a real PDF uploaded to the
  ready state; parse with no AI configured showing "We could not reach the AI service" and staying
  retryable; and, with the CV row set directly in the dev database (test data, not a live parse):
  parsing, failed (`no_profile_found`, `ai_unavailable`, `text_too_long`), and parsed with a
  directly inserted draft; delete with confirm removed the CV and the draft (0 rows left).
- Compared with the Onboarding board rendered from its saved source: the left card matches
  (stepper, Migo bubble, heading, dashed dropzone, file card with progress and step list, trust
  box, pill buttons). Differences are exactly the seven Deviations above, plus the board's wordmark
  header that the app shell replaces.
- Console: no errors. Network: only the expected 502s from the parse call with no AI configured
  and a favicon 404.
- Not run: a live DeepSeek parse (no `AI_CHEAP_MODEL` or `DEEPSEEK_API_KEY` in `.env`), and a DOCX
  upload through the page (a PDF was used; the DOCX path is covered by the engine tests and the
  feature 3a end-to-end run through the same routes).
- Local state changed for this check: the dev database was migrated to `0004` and the engine
  container rebuilt. The test account `e2e-3c-*@example.test` remains in the dev database.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":12209,"specSha256":"0c9424f8032c606dc02fe56e824c701cb76694dec06a3507bf787f2a540e1476","branch":"refs/heads/feature/cv-upload-and-parse-status-screen","head":"80679ab5a200a14efb0e1c286e5412438c96a694","baseRef":"refs/heads/main","baseCommit":"bfa584fb4b5fbb0ba844363d5a403008eb5e3997","sourceTree":"96647047ac12afecf0f1220c5a5948741979f670","landing":"local-merge","absentOptional":[]} -->

## Findings

### 3c/F-75 [P2] closed - A parse that never finishes leaves the user no way out except "Check again"

**File:** web/src/routes/_app/onboarding.tsx:265
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The `parsing` view offers no delete, no replace and no retry, and after the 3-minute poll limit it offers only "Check again". Engine F-71 (a row stuck in `parsing` until the engine restarts) makes that state permanent, so the user sees "taking much longer than usual" indefinitely and cannot remove or replace the CV (ready, parsed and failed all have a delete or replace control). Reachable only through that engine fault, not reproduced here.
**Suggested fix:** Once `elapsedMs >= POLL_LIMIT_MS`, also show `DeleteControl` (or the replace action), and make the engine side recoverable (F-71).
**Resolution:** Fixed: the parsing view now has Delete this CV (with confirm) at all times, including after the 3-minute poll limit; seen in the browser.
Closed 2026-11-10 by /audit independent: re-read onboarding.tsx; `DeleteControl` renders in the parsing view at all times, after the poll limit too, and `remove()` is safe mid-parse (engine `run_parse` returns without writing when the row is gone). No new defect found.

### 3c/F-79 [P3] closed - Copy promises a review step that is not built, and the dashboard card never goes away

**File:** web/src/routes/_app/dashboard.tsx:78, web/src/routes/_app/onboarding.tsx:190
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The spec says nothing may claim unbuilt features. The dashboard card says "a profile draft you can review" and the page intro says "You'll review every fact before anything is scored or written"; review, scoring and writing do not exist yet (the parsed view does say so honestly). The dashboard card also reads "Upload your CV to begin" for a user who already uploaded or parsed one.
**Suggested fix:** Reword to what exists ("Migo reads it into a draft of your profile"), and either hide the card once a CV exists or change its text.
**Resolution:** Fixed: the intro now says it is a draft and nothing is scored or written from it yet; the dashboard card reads "Your CV" with "Open CV page".
Closed 2026-11-10 by /audit independent: re-read dashboard.tsx and the page intro; neither claims review, scoring or writing. (F-83 covers the trust box.)

### 3c/F-80 [P3] closed - Under reduced motion the progress bar freezes at 40%, which reads as a percentage

**File:** web/src/styles.css:225
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The global reduced-motion rule sets `animation: none !important`, so the indeterminate fill (`w-2/5`) stops at the left, a static 40% bar, which contradicts the "no percentage is shown" deviation. The CSS comment ("still under reduced motion") is wrong: the animation does not run there.
**Suggested fix:** Under `prefers-reduced-motion`, render the fill full-width at low opacity (or hide the track) and fix the comment.
**Resolution:** Fixed: under reduced motion the bar is a full-width dimmed bar, and the CSS comment says so.
Closed 2026-11-10 by /audit independent: `.indeterminate` under `prefers-reduced-motion` is `width: 100% !important; opacity: 0.45`, which beats the global `animation: none` rule and the `w-2/5` class; the comment is correct.

The other findings of this build (F-76 to F-78 and F-81 to F-84, all P3) are unresolved and stay in the live ledger with their IDs.

## Independent review

Original passing receipt for checkpoint `80679ab5a200a14efb0e1c286e5412438c96a694`, copied unchanged:

````markdown
**Status:** passed
**Target commit:** 80679ab5a200a14efb0e1c286e5412438c96a694
**Base commit:** bfa584fb4b5fbb0ba844363d5a403008eb5e3997
**Base ref:** main
**Spec hash:** 0c9424f8032c606dc02fe56e824c701cb76694dec06a3507bf787f2a540e1476
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-10T11:45:17Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-10T11:52:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `shasum -a 256 blueprint/context/current-feature.md`, `git status --porcelain`: pass (all match the request; only review.md and findings.md differ)
- `npm run lint` (web): pass
- `npm run typecheck` (web): pass
- `npm test` (web): pass (123 passed, 1 skipped)
- `npm run build` (web): pass

## Evidence

- Reviewed the full `bfa584f..80679ab` delta: onboarding.tsx, components/cv/parts.tsx, lib/cv-api.ts, lib/cv-view.ts, styles.css, dashboard.tsx, AuthForm.tsx, the two test files, docs; read web/src/server/cv/http.ts and the engine delete and parse paths to check limits, error codes and delete-while-parsing.
- No P0 or P1 found. User text (filename, headline, roles) renders only as React text. The browser maps every error to fixed copy (codes are regex-checked and never displayed). Polling is one `refetchInterval` plus one 5 s elapsed timer cleared on unmount, stopping on any non-parsing state or at 3 minutes. Delete while parsing is safe (engine run_parse writes nothing when the row is gone). The 5 MiB, PDF/DOCX client check matches the engine's and the server's early cut-off.
- Ledger re-examination: F-75, F-79 and F-80 closed. F-76 (focus after Build/Try again not repaired), F-77 (file-problem replaces the failure message beside the wrong buttons) and F-78 (ai_not_configured left with no retry and a persisted failed state) reopened at P3. F-81 left open with added notes.

## Findings

- New, all P3 open: F-82 (draft 401 not redirected), F-83 (trust box names DeepSeek), F-84 (large `role="status"` regions).
- Reopened, P3 open: F-76 (severity lowered from P2), F-77, F-78. Still open: F-81.
- Closed: F-75, F-79, F-80.
- No P0 or P1 is open or fixed, so the receipt passes. The P3 entries are non-blocking but F-76, F-77 and F-78 are repairs that did not fully hold and are worth fixing.

## Remaining risk

- The live DeepSeek parse was not run (no model or key configured).
- A DOCX was not uploaded through the page (a PDF was used).
- No automated component or browser test exists in the repo; the evidence for page behaviour was a scripted browser pass, and the polling, replace and 401 logic in the page is untested (F-81).
- I did not re-run the browser pass; the focus and live-region findings come from reading the code.
````

## Try guide

Skipped: `/check guide` is user-run and was not available to the completing session (the same decision the user made for 3a). Run `/check guide latest` for a walkthrough. The live DeepSeek parse was not run because `.env` had no AI model or key.
