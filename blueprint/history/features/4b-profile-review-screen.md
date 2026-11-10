# Feature: Profile review screen

**From build-plan:** feature 4b
**Build attempt:** 1
**Branch:** feature/profile-review-screen
**Status:** verified

## Goal

A signed-in user opens `/profile` and reviews the facts the parse found: sees which are still
unconfirmed, confirms each (or all), corrects any, adds one the parse missed, and deletes a wrong
one, using only the 4a routes. The unconfirmed state is always visible, in text and not by colour
alone. After this, "the profile" has confirmed facts that later features may cite.

## Design reference

Approved canvas `https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q`, **Profile** board (saved as
`blueprint/reference/profile.dc.html` from the canvas file `project/Profile.dc.html`) and the
**States** board (`states.dc.html`: empty card, skeleton loading, error card).

Required match: the page header ("Career profile", the sentence "Everything Jobmigo writes or
scores comes from facts you have confirmed here."), the four setup-progress cards, the white
rounded Experience card with role rows (role in bold, "company · dates", a state pill and an
edit icon button, bullets below), the Skills chip card, Fredoka and Nunito from the tokens, pill
buttons (primary `#B04A27`), 44px targets, reduced motion.

Deviations, each stated in the final packet:
1. No variant tabs (4c), and no right-hand column: Job preferences (feature 5), Alerts (10) and
   Your data (17) are not built, so the content is one centred column.
2. "Confirm and continue" is "Confirm all" (the next onboarding step is not built); "Upload new
   CV" links to `/onboarding`.
3. Skill chips: the board's solid/dashed outline means "used in a role"; here it means confirmed
   (solid) or unconfirmed (dashed with the words "Unconfirmed" in the chip's accessible text and a
   visible legend), because that is the state this feature manages.
4. Achievements, Projects and Education cards are added in the Experience card's style (the board
   shows only Experience and Skills; the data has these kinds).
5. The setup-progress cards: Upload CV "Done", Review profile "N of M confirmed", the last two
   "Not started" (not links, those steps are unbuilt).
6. The page is inside the app shell; the sidebar's "Career profile" item becomes a link.
7. The credits box in the board's sidebar is not built (billing).

## In scope

1. A typed client for the profile routes (`web/src/lib/profile-api.ts`, same result shape as
   `cv-api.ts`) and a pure view-model (`web/src/lib/profile-view.ts`): field specs per kind,
   form to request-body mapping and back, client-side checks that mirror the parse bounds, copy
   for every error code, counts and the progress summary.
2. The `/profile` route: loading skeleton, empty state (no parsed draft: card linking to
   `/onboarding`), load-failed card with retry, and the review view: header with Confirm all and
   Upload new CV, progress cards, Experience, Skills, Achievements, Projects, Education.
3. Per-fact controls: Confirm, Edit (inline form with labels, per-field errors tied to the
   input, Save and Cancel), Delete (inline confirm); per section Add; headline and summary
   editing. One mutation at a time (controls disabled while one runs). Announcements for
   "Saved", "Confirmed", "Deleted" in a polite live region; focus returns to a sensible element
   after every transition (edit button after save or cancel, the section heading after a delete).
4. The sidebar link to `/profile`, and the onboarding "draft ready" view pointing to it
   ("Review your profile" button) instead of saying review is not built.
5. Copies of the board sources for the design check, docs and the README status row.

## Out of scope

- Tracks, variants and what each emphasises (4c), job preferences (5), alerts, export and
  account deletion, reordering facts, undo, merging several CVs, and any engine change.
- A browser test harness (none configured); evidence is a scripted browser pass.

## Build loop

`blueprint/config.json`: `stepReview: feature`, `checkpointCommits: disabled`; Continuous Mode.
Independent review is required (personal data, edit and delete).

## Build steps

- [x] 1. **Client and view model.** `profile-api.ts` (`getProfile`, `patchProfile`, `addItem`,
  `patchItem`, `confirmItem`, `deleteItem`, `confirmAll`; each returns `{ ok, data }` or `{ ok:
  false, code }`, never throws on an HTTP error, `fetchFn` injectable) and `profile-view.ts`.
  Done when Vitest proves: the request path, method and JSON body of each call; the stable-code
  and network-failure handling; form to body and back for every kind (empty strings become null,
  bullets from lines, `isCurrent` with an end date, trimming); the client checks (lengths, date
  pattern `YYYY` or `YYYY-MM`, required fields); copy for every code with no raw message or code
  shown; counts and progress text; and that only changed fields are sent on edit (`npm test`).
- [x] 2. **The page.** `web/src/routes/_app/profile.tsx` plus `web/src/components/profile/*`;
  every state and control in In scope items 2 to 4; accessible by design (real buttons, labels,
  `aria-describedby` on errors, a polite live region, focus rules, 44px targets, reduced motion);
  regenerate `routeTree.gen.ts`. Done when lint, typecheck and build pass and, against the local
  engine with a throwaway account and a seeded draft, every action works in the browser: confirm
  one, confirm all, edit with a validation error then a save, add, delete with confirm.
- [x] 3. **Design check, evidence and docs.** Capture the screen at 1440 and 390 wide in every
  state beside the Profile and States boards (rendered from their saved sources); list each
  difference and match it to the Deviations; check console and network; update
  `docs/technical-design.md` and the README status row. Done when each state was seen, the
  differences are exactly the Deviations, the console shows no errors, and the full Verify passes.
- [x] 4. **Repair review findings F-93 to F-101.** Per-skill panel state, load-failure copy, focus
  after Confirm, Confirm all, the headline editor and the skill panel, one error per failure shown
  in its row, repeat announcements, no stale facts after a failed read, collapsed-whitespace length
  check, chip names and panel relationship. Done when each is seen in the browser, the new unit
  tests pass, and the full Verify passes.

## Files / areas

`web/src/lib/profile-api.ts`, `web/src/lib/profile-view.ts`, `web/src/routes/_app/profile.tsx`,
`web/src/components/profile/*`, `web/src/routes/_app.tsx`, `web/src/routes/_app/onboarding.tsx`,
`web/src/routeTree.gen.ts`, `web/tests/profile-view.test.ts`, `web/tests/profile-api.test.ts`,
`blueprint/reference/profile.dc.html`, `docs/technical-design.md`, `README.md`.

## Data / contracts

Consumes the 4a web routes and bodies unchanged (`/api/profile`, `/api/profile/items/:kind`,
`.../:id`, `.../:id/confirm`, `/api/profile/confirm-all`); statuses `extracted`, `confirmed`,
`edited`; error codes `not_found` (also "no draft yet" on the read), `validation_failed`,
`limit_reached`, `already_exists`, `unauthorized`, `engine_unavailable`.

User-controlled text (every fact, headline, summary) is rendered as React text only. The page
never builds an id from anything but a server response. After each successful change the profile
is re-read (the version is the server's); the page holds no copy that can drift.

Labels: `extracted` shows "Unconfirmed", `confirmed` "Confirmed", `edited` "Edited by you".
Progress counts `confirmed` and `edited` as reviewed.

## Testing

Vitest for the two lib modules (no DOM library installed or added). The page is checked in a real
browser as step 3 describes.

## Notes for the AI

- Follow `onboarding.tsx` and `components/cv/parts.tsx` for structure, tokens, button classes,
  live regions and focus handling; reuse them rather than copying. The previous reviews found
  focus loss, duplicate alerts, no way out of a busy state, and a retry offered where it cannot
  help: avoid each of those here.
- Honest copy: nothing claims tracks, preferences or export exist. Do not add a dependency.

## Open questions

None.

## Evidence (recorded during the build)

- Browser pass (headless Chrome, local web, engine and database, a throwaway local account,
  1440 and 390 wide) saw: the empty state; a seeded draft (test data inserted directly) with all
  five sections and "0 of 8 reviewed"; Confirm (live region said "Confirmed.", status changed);
  Edit with a validation error (field marked invalid, error tied to it, focus in the first field)
  then a save (status "Edited by you", focus back on the Edit button); Add skill with a duplicate
  (calm 409 message) then a new skill (focus on the section heading); Delete skill (focus on the
  safe choice, then on the section heading, chip gone); Confirm all (progress "All reviewed",
  button disabled); headline edit; and the onboarding "Review your profile" link.
- Compared with the Profile board rendered from its saved source: header, progress cards,
  Experience card with role rows, and the Skills chip card match. Differences are the Deviations
  above, plus: the pill reads "Unconfirmed" (board: "Needs review"), the fourth progress card
  reads "First evaluation" (board: "Your shortlist"), and the skill chip fill and text are the
  token colours.
- Console: no errors. Network: only expected statuses (404 for no draft, 409 for the duplicate).
- Local state changed: the dev database was migrated to `0005`, the engine container rebuilt, and
  the test CV rows removed. Test accounts `e2e-4b-*@example.test` remain in the dev database.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":9629,"specSha256":"ac4c1e22145c159f794198eb77629216ce1dd7c2c74fca0cc2f5b125de5f6d82","branch":"refs/heads/feature/profile-review-screen","head":"f51fd21b6eca7a53e6c450c4b644cc39681a09fc","baseRef":"refs/heads/main","baseCommit":"9c56d4608639a401ee4ad0c136093f09c81b172e","sourceTree":"ac9d9c39e82207534cbe5220c19a16da82c4d301","landing":"local-merge","absentOptional":[]} -->

## Findings

_No finding was closed in this build._

Findings F-93 to F-103 of this build (P2 and P3) were repaired or are recorded as open P3; they are not closed, so they are kept in the live ledger with their IDs.

## Independent review

Original passing receipt for checkpoint `f51fd21b6eca7a53e6c450c4b644cc39681a09fc`, copied unchanged:

````markdown
**Status:** passed
**Target commit:** f51fd21b6eca7a53e6c450c4b644cc39681a09fc
**Base commit:** 9c56d4608639a401ee4ad0c136093f09c81b172e
**Base ref:** main
**Spec hash:** ac4c1e22145c159f794198eb77629216ce1dd7c2c74fca0cc2f5b125de5f6d82
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-10T12:40:00Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-10T13:10:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Handoff

Review the active spec and the complete `<base>..<target>` delta in a fresh
session or isolated subagent without the builder conversation. Run all Audit lenses from scratch.
Run Check when required above. Do not edit product code, accept findings, or
reuse the existing findings as the review scope.
This is the second review of this feature (the first passed with P2/P3 findings that were then repaired); review the whole delta again, not only the repair.

## Commands

- `git rev-parse HEAD`, `git merge-base HEAD main`, SHA-256 of `blueprint/context/current-feature.md`: pass (all match the request; only review.md differed in the working tree)
- `git diff 9c56d46..f51fd21` (15 files; web files read in full): pass
- `npm run lint` (web): pass
- `npm run typecheck` (web): pass
- `npm test` (web): pass (150 passed, 1 skipped)
- `npm run build` (web): pass

## Evidence

- Target, base and spec hash verified before review.
- Repairs confirmed by reading `web/src/routes/_app/profile.tsx` and `web/src/components/profile/facts.tsx`: F-93 (`key={selected.id}` on the panel row), F-94 (own load-failure card, no stale facts), F-95 (focus to the Edit button after Confirm, title after Confirm all, headline input on open, chip on panel close), F-96 (one inline error per failure via `serverError`, `rowError`, `addError`; page banner only for `not_found` and Confirm all), F-97 (alternating zero-width suffix), F-100 (whitespace collapsed before the length check and in the sent body, covered by a test), F-101 (chip name, `aria-controls`, focus into `#skill-panel`). F-98 and F-99 remain open as recorded (partial repairs, accurately described).
- Client bounds checked against `engine/src/engine/profile/models.py` and `cv/limits.py` (lengths, bullets, date, extra fields forbidden); user text is rendered as React text only, ids come from server responses, API client never throws and maps unsafe codes to `unexpected`.
- No new P0 or P1. Two new P3 findings; no repair was found to be ineffective.

## Findings

- New: F-102 (P3), F-103 (P3)
- Previously raised, status unchanged: F-98 (P3, open), F-99 (P3, open); F-93 to F-97, F-100, F-101 confirmed fixed

## Remaining risk

- The page itself has no automated test and was not run in a browser by this reviewer (no servers started); focus and live-region behaviour was verified by reading the code (see F-99).
````

## Try guide

Skipped: `/check guide` is user-run and was not available to the completing session (the same decision the user made for 3a). Run `/check guide latest` for a walkthrough. The live DeepSeek parse was not run because `.env` had no AI model or key.
