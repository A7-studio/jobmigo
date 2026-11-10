# Feature: Add a job screen

**From build-plan:** feature 29c
**Build attempt:** 1
**Branch:** feature/add-a-job-screen
**Status:** verified

## Goal

A signed-in user can open Jobs, add a job by pasting a link (the engine reads the page when the site
allows it) or by pasting the posting text, confirm company and title, and see their saved and
dismissed jobs. Nothing is evaluated or ranked yet.

## Design reference

The Jobs board (Jobmigo canvas, `project/Jobs.dc.html`, saved to `blueprint/reference/jobs.dc.html`):
page title and subtitle, a card of rows with a 44px initial tile, title, a "company · place" line, a
small meta line and a right-hand badge. The board shows discovery, fit bands, filters, track chips
and AI credits, none of which exist yet. The Job board (detail) is not used. Decisions for this
feature, recorded as deviations: the subtitle says what the page really does; rows show only stored
facts (company, title, place, source host, date added, a "Check this posting" badge when the cleaner
flagged it, saved or dismissed); the right-hand badge and bookmark are replaced by Dismiss or
Restore and Delete; there is no discovery summary, track chips, filters, load more or credit meter;
the add form and the "read the text we saved" disclosure have no board.

## In scope

- Route `/jobs` in the app shell; the sidebar's Jobs item becomes a link.
- The list with two views (Saved, Dismissed), loading, empty, error and signed-out handling.
- Add a job: a link path (read the page, then confirm company, title, place and the text) and a
  paste path; refusals from the engine shown calmly with a way forward (paste the text).
- Dismiss, restore and delete (with a question); a disclosure to read the saved text.
- A view model with tests, and the docs.

## Out of scope

Evaluation, fit, tracks on jobs, discovery, filters, search, pagination, editing a saved job,
extracting company and title from text, the Job detail screen, notifications.

## Build steps

- [x] 1. **View model and tests.** `web/src/lib/jobs-view.ts`: form checks that mirror the engine
  bounds (company 1 to 120, title 1 to 200, place up to 120, text 5 to 100,000, link up to 2,000,
  whitespace collapsed the way the engine does it), calm copy for every error code (including the
  fetch codes `fetch_blocked`, `robots_disallowed`, `robots_unreadable`, `not_a_page`,
  `too_large`, `fetch_failed`, `rate_limited`, and `already_exists`, `limit_reached`,
  `validation_failed`, `network`, `not_found`), the source-host label (http and https only, never a
  link built from anything else), the initial tile letter and a date label. Done when tests pass.
- [x] 2. **The list.** `web/src/routes/_app/jobs.tsx` and `web/src/components/jobs/*` plus the
  sidebar link: Saved and Dismissed views (`aria-pressed` chips), rows per the board, Dismiss or
  Restore, Delete with a question, the text disclosure, the review badge with its explanation,
  loading, empty ("No jobs yet"), failed-load, one change at a time, a polite live region and the
  focus rules used on `/profile`. Done when, in the browser against the local engine with a
  throwaway account and seeded jobs, every action works, 390 wide has no horizontal scroll and the
  console is clean.
- [x] 3. **Add a job.** The add card: link field with "Read the page", a "paste the text instead"
  path, the confirm form (company, title prefilled from the page title, place, text), save, and
  every refusal state with copy and a next step; a link kept when switching to paste. Done when the
  browser pass covers a paste save, a duplicate, a bad form, a blocked link (a private address) and
  a real public page, and each state matches the copy.
- [x] 4. **Evidence and docs.** Captures at 1440 and 390 wide beside the Jobs board with each
  difference listed against the Deviations; `docs/technical-design.md` and the README row. Done when
  the full Verify passes.

## Files / areas

`web/src/routes/_app/jobs.tsx`, `web/src/routes/_app.tsx`, `web/src/components/jobs/*`,
`web/src/lib/jobs-view.ts`, `web/tests/jobs-view.test.ts`, `web/src/routeTree.gen.ts`,
`blueprint/reference/jobs.dc.html`, `docs/technical-design.md`, `README.md`.

## Data / contracts

Uses the existing routes only: `GET /api/jobs?status=`, `POST /api/jobs`, `PATCH` and `DELETE
/api/jobs/{id}`, `GET /api/jobs/{id}` (the saved text), `POST /api/jobs/fetch`. A job is
`{id, company, title, location, sourceUrl, status, flag, findings, createdAt}`. A fetched page is
`{text, title, finalUrl, truncated}` and is not stored until the user saves it with the paste
route (the link field value or the final address is sent as `url`). When a fetched text was cut
(`truncated`) the form says so. Pasted and fetched text are rendered as React text only; a link to
the original posting is shown only for `http` and `https` addresses, with `rel="noopener
noreferrer"`. Error codes are shown through calm copy, never raw.

## Testing

Vitest for the view model. A scripted browser pass (kept out of the repo) for the list, each action
and each add path against the local engine, including one real public page. No new server routes.

## Notes for the AI

Match the `/profile` conventions: `Problem` card, `BTN` styles, one mutation at a time, a polite
live region, focus after each action, no raw codes, honest copy (nothing here evaluates or ranks).
No new dependencies.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":5385,"specSha256":"c0346c16bd4e6209bfab888732e8d05743eaa49d3f80f0e686d4843ce6b1b9c7","branch":"refs/heads/feature/add-a-job-screen","head":"1fac7babaae076c5d230ae7f4c730631f2aade8b","baseRef":"refs/heads/main","baseCommit":"74d05e4061b4d68755a10cf01dca4ac0040ef2f5","sourceTree":"2fe7d5db268ad8f0b2c105bf429bb6cf9ae3440c","landing":"local-merge","absentOptional":[]} -->

## Findings

_No finding was closed in this build._

Findings of this build: the closed and resolved entries are archived above; entries still open or fixed (awaiting a later audit) stay in the live ledger with their IDs, so all are kept in the live ledger with their IDs.

## Independent review

Original passing receipt for checkpoint `1fac7babaae076c5d230ae7f4c730631f2aade8b`, copied unchanged:

````markdown
**Status:** passed
**Target commit:** 1fac7babaae076c5d230ae7f4c730631f2aade8b
**Base commit:** 74d05e4061b4d68755a10cf01dca4ac0040ef2f5
**Base ref:** main
**Spec hash:** c0346c16bd4e6209bfab888732e8d05743eaa49d3f80f0e686d4843ce6b1b9c7
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-10T18:55:55Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-10T19:10:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `sha256sum blueprint/context/current-feature.md`: pass (HEAD, base and spec hash match the request; only review.md differed)
- `npm run lint` (web): pass
- `npm run typecheck` (web): pass
- `npm test` (web): pass (189 passed, 1 skipped)
- `npm run build` (web): pass
- `uv run ruff check .` (engine): pass
- `uv run mypy` (engine): pass
- `uv run --env-file ../.env pytest -q` (engine): pass (462 passed, 9 skipped)

## Evidence

- Read in full: web/src/routes/_app/jobs.tsx, web/src/components/jobs/add-job.tsx, job-row.tsx, web/src/lib/jobs-view.ts, jobs-api.ts, web/tests/jobs-view.test.ts, the _app.tsx sidebar diff, docs and README diff.
- No `dangerouslySetInnerHTML`; posting text, title, company and place render as React text; `href` only from `safeHref` (http/https, no credentials) with `target="_blank"` and `rel="noopener noreferrer"`; the engine revalidates the saved url (`url_key`).
- Add flow: Close, Back, Save and Read are disabled while a request runs and implicit submit is blocked by the disabled default button; a 401 goes to sign-in from list, actions, fetch and save; state updates after unmount are harmless; failed reads hide stale rows; view chips are disabled during a change.
- Error copy never shows codes (tested and read); copy does not claim to evaluate or rank.
- Measured `TZ=America/New_York`: the day count in `addedLabel` gives 0 for one calendar day across a spring-forward (F-120).
- Not compared against the Jobs board capture or run in a browser by this reviewer.

## Findings

- F-120, F-121, F-122, F-123, F-124, F-125 (all P3, open). No P0 or P1.

## Remaining risk

- No DOM test library: the add state machine, focus rules and cache invalidation rest on the builder's manual browser pass (F-125).
- Visual match to blueprint/reference/jobs.dc.html and the 390 px layout were not re-verified by this review (no servers or browser started).
````

## Try guide

Skipped: `/check guide` is user-run and was not available to the completing session (the same decision the user made for 3a). Run `/check guide latest` for a walkthrough. The live DeepSeek parse was not run because `.env` had no AI model or key.
