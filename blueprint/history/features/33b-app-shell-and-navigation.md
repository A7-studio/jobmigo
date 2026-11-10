# Feature: App shell and navigation

**From build-plan:** feature 33b
**Build attempt:** 1
**Status:** verified
**Branch:** feature/app-shell-and-navigation

## Goal

Give the signed-in app the four-place structure the approved 33a boards show: a sidebar of
Today, Jobs, Profile and Settings (a fixed bottom bar on phones), `/today` in place of
`/dashboard`, a basic `/settings` page, and an empty job workspace page at `/jobs/$jobId`
with the four steps that features 8, 11, 12 and 15 fill in later. The shell adds no new
data and no AI behavior.

## Design reference

- Approved boards, saved in the repo: `blueprint/reference/today.dc.html`,
  `jobs.dc.html`, `job.dc.html` (the job workspace), `settings.dc.html`. Canvas (type
  Design): https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q, version `1794351108-fce8`.
  The built UI must match these boards; a design change goes to the canvas first.
- Locked tokens: `prototypes/theme.css`, already ported into the app stylesheet.
- Built files this changes: `web/src/routes/_app.tsx` (sidebar),
  `web/src/routes/_app/dashboard.tsx` (becomes Today), `web/src/components/AuthForm.tsx`
  (post sign-in and sign-up redirects), `web/src/components/jobs/job-row.tsx` (Open link).
- Phone navigation (user request): below the app's `md` breakpoint the four places sit in
  a fixed bar at the bottom of the screen with an icon and a label each; the top bar keeps
  the logo and Sign out.

## In scope

1. **Sidebar:** Today, Jobs, Profile, Settings, then the signed-in name and Sign out. The
   four greyed-out "Soon" items are removed. "Career profile" in the sidebar becomes
   "Profile" (the profile page keeps its own heading). No credits meter.
2. **Phone bar:** below `md`, the four places form a fixed bottom bar; every target is at
   least 44px; the page has enough bottom space that nothing hides behind the bar; no
   horizontal page scroll at 390px.
3. **`/today`:** the current dashboard page, moved and retitled "Today". Its content is
   not redesigned here; the queue of next actions is feature 9. Its loading, failed and
   signed-out states keep working with "Today" wording.
4. **`/dashboard` redirect:** the old address redirects to `/today` (replacing the history
   entry). Sign-in, sign-up and Google sign-in land on `/today`.
5. **`/settings`:** account details (name and email, read only), Sign out, and a "Later"
   group (Your data: export and delete account; Plan and billing; Telegram) that shows
   what is not part of this version. Loading, failed with retry, and signed-out states.
6. **`/jobs/$jobId` workspace shell:** a Back to jobs link, the job header (title, company
   and location from the saved job), and the four steps Fit, CV and letter, Outreach and
   Track as tabs, each showing a short honest "not built yet" panel. States: loading, job
   not found, failed with retry, signed out. The Jobs rows get an "Open" link to it.
7. **Tests** for the route registration, the redirect, the navigation list and the step
   tab keys.

## Out of scope

- The Today queue (feature 9), the Fit step (8), kit, CV and letter (11 and 12), outreach
  (15), tracking and stages (later features). The tab panels hold only a placeholder.
- Jobs list changes: stage views, Keep and Skip, the Filtered out view, fit labels. The
  user decided (2026-11-11): keep the Saved and Dismissed views as built, and keep the
  row Delete as built. A skipped job moves under Closed as "Skipped by you", and Delete is
  re-decided, when the stage views are built.
- Settings actions: no Change, Export or Delete account buttons (nothing exists behind
  them). Billing, plan and Telegram stay labelled Later.
- Any engine, database or API change. Any new dependency.
- Redesigning onboarding, the Profile page, the homepage or the sign-in pages.

## Build loop

`workflow.stepReview` is `feature`: work through the steps, then present one review
packet. `workflow.checkpointCommits` is `disabled`: no step commits. `/complete` makes the
single feature commit.

## Build steps

- [x] 1. Add `web/src/lib/app-nav.ts` with the four places (label and path), the signed-in
  landing path `/today`, and a pure `nextStep(current, key)` for the workspace tab keys
  (ArrowLeft, ArrowRight, Home, End; any other key returns null), plus the step list
  Fit, CV and letter, Outreach, Track. Add `web/tests/app-nav.test.ts` for them.
  **Done when:** the test file passes with `npm test`, covering labels and order, the
  landing path, wrap-around and unknown keys.
- [x] 2. Create `web/src/routes/_app/today.tsx` from `dashboard.tsx` ("Today" wording,
  `head` title "Today | Jobmigo"). Replace `dashboard.tsx` with a route that has no
  component and only a `beforeLoad` redirect to `/today` with `replace: true`. Point
  `AuthForm.tsx` (both places) at `landingPath`. Let the build regenerate
  `routeTree.gen.ts`.
  **Done when:** `npm run typecheck` and `npm run build` pass, nothing but the redirect
  route mentions `/dashboard`, and `web/tests/app-routes.test.ts` shows `/dashboard`
  redirects to `/today` and the route tree contains `/today`.
- [x] 3. Rebuild the sidebar in `_app.tsx` from `app-nav.ts`: four links with icons (inline
  SVG; no new dependency), the greyed-out items removed, active page marked through the
  router's `aria-current`, and the phone bottom bar below `md` (fixed, 44px targets, safe
  area inset, bottom padding on `<main>`).
  **Done when:** in the browser at 1440px the sidebar shows exactly Today, Jobs, Profile
  and Settings plus Sign out; at 390px the bar is fixed at the bottom, the top bar keeps
  logo and Sign out, nothing sits under the bar, there is no sideways scroll, and every
  control measures at least 44px.
- [x] 4. Add `web/src/routes/_app/settings.tsx` per the Settings board: Account (name and
  email from `useMe`, read only), Sign out (reusing the same sign-out as the sidebar,
  moved to a shared function if needed), and the Later group with a "Later" tag and no
  button. Loading, failed with retry, and signed-out states as on Today.
  **Done when:** it renders at 1440px and 390px, shows the signed-in name and email as
  text, Sign out returns to `/sign-in`, no inert button appears, and `/settings` is in the
  route tree test.
- [x] 5. Add `web/src/routes/_app/jobs_.$jobId.tsx` and a `JobWorkspace` component under
  `web/src/components/jobs/`: Back to jobs, the header from `getJob`, and four tabs with
  `role="tablist"`, `tab`, `tabpanel`, `aria-selected`, roving focus and the key handling
  from `nextStep`. Each panel says plainly that the step is not built yet and names what it
  will hold; nothing implies a result. States: loading (`aria-busy`), `not_found`, other
  failure with Retry, `unauthorized` to sign-in. Add the "Open" link on each Jobs row.
  **Done when:** opening a saved job from the list shows its title and company and the
  four tabs; arrow keys move between tabs; a made-up id shows the not-found state; Back to
  jobs returns to the list; `/jobs/$jobId` is in the route tree test.
- [x] 6. Check the result against the boards in the browser and finish. Compare
  Today, Jobs (sidebar and phone bar only), the workspace and Settings with the saved
  boards at 1440px and 390px; check the console and network for errors; record the
  differences from the boards in the step notes.
  **Done when:** the differences are listed in the spec, no console errors, and
  `Verify` passes.

## Files / areas

- New: `web/src/lib/app-nav.ts`, `web/src/routes/_app/today.tsx`,
  `web/src/routes/_app/settings.tsx`, `web/src/routes/_app/jobs_.$jobId.tsx`,
  `web/src/components/jobs/job-workspace.tsx`, `web/tests/app-nav.test.ts`,
  `web/tests/app-routes.test.ts`.
- Changed: `web/src/routes/_app.tsx`, `web/src/routes/_app/dashboard.tsx` (redirect only),
  `web/src/components/AuthForm.tsx`, `web/src/components/jobs/job-row.tsx`,
  `web/src/routeTree.gen.ts` (generated).
- Not touched: `engine/`, database schema and migrations, `web/src/server/`.

## Data / contracts

No stored data, API or engine change. Routes after this feature:

| Address | Behavior |
| --- | --- |
| `/today` | signed-in home (was `/dashboard`) |
| `/dashboard` | redirects to `/today`, replacing the history entry |
| `/jobs` | unchanged (Saved and Dismissed views, Add a job, Delete as built) |
| `/jobs/$jobId` | job workspace shell; `$jobId` is the saved job's id from the existing `GET /api/jobs/:id` |
| `/profile` | unchanged |
| `/settings` | account details, sign out, Later group |

- The signed-in area stays behind the existing `_app` session check; the workspace loads
  the job through the existing owner-scoped API, so another user's id returns the same
  `not_found` as a missing one. The page never renders a job it did not receive from it.
- Job text (title, company, location) is rendered as plain text, never as markup.
- The selected workspace step is component state, not part of the address, so later
  features decide whether a step gets its own address.
- Sign out in the sidebar and on Settings is the same action: end the session, clear the
  query cache, go to `/sign-in`.

## Testing

- Baseline observed on `main` at `302ac7a` before this spec: web lint, typecheck and
  build passed; web tests 189 passed, 1 skipped; engine ruff, format check and mypy
  passed; engine tests 462 passed, 9 skipped.
- New automated tests (no DOM test library is installed, so none is added): the navigation
  list, landing path and tab key handling as pure functions; the route tree contains
  `/today`, `/settings` and `/jobs/$jobId`; the `/dashboard` route throws a redirect to
  `/today`.
- Browser evidence (the dev server on port 3000 is started by the user or `npm run dev`;
  a local test account is needed to sign in, created on localhost sign-up or supplied by
  the user, never a real password in chat): the sidebar and phone bar, `/dashboard`
  redirecting, the Settings page, the workspace tabs with the keyboard, and not-found.
  No claim of visual or runtime evidence beyond what was run.
- The `Verify` command from `AGENTS.md` must pass.

## Notes for the AI

- Match the boards. Where the built UI cannot match yet, record it; do not invent copy.
  Copy stays honest: no outcome promises; the workspace panels say "not built yet".
- Keep existing tokens and classes (`BTN`, `BTN_PRIMARY`, `NAV_ITEM`); add no new fonts,
  tokens or component library.
- Accessibility: one `h1` per page; focus moves to the page heading after a route change
  where the existing pages do it; tabs follow the ARIA tabs pattern; the live status
  wording follows the Jobs page.
- Motion only on state changes, and none under reduced motion.
- Name the workspace route file `jobs_.$jobId.tsx` (the trailing underscore keeps it a sibling
  of `jobs.tsx`; the built `/jobs` page has no `Outlet`, so a nested child would never render).
- Do not change the Jobs list behavior (see Out of scope) and do not touch the engine.
- `/today` keeps the dashboard's current content. Do not add the queue early.

## Differences from the boards, already known

- Breakpoint: boards switch to the bottom bar at 720px; the app uses its `md` breakpoint
  (768px) so the shell follows the stylesheet. Decide in step 6 if that needs a change.
- Settings: the boards show Change, Export my data and Delete account as active. The app
  has nothing behind them, so they appear under Later with no button.
- Jobs: the boards' stage views, Keep and Skip, Filtered out and fit labels wait for
  features 8, 9 and 10. The built Dismissed view and row Delete stay (user decision).
- Workspace: the boards show one "Prepare application" button, a review state and sample
  data; the shell shows only the header and the four placeholder steps.

## Step notes

**Steps 1 to 5 (built, automated checks passed)**

- Built: `app-nav.ts`, `use-sign-out.ts` (shared sign-out), `today.tsx`, redirect-only `dashboard.tsx`, `settings.tsx`, `jobs_.$jobId.tsx` with `job-workspace.tsx`, the new sidebar and phone bar in `_app.tsx`, the Open link in `job-row.tsx`, `AuthForm.tsx` landing on `/today`, tests `app-nav.test.ts` and `app-routes.test.ts`.
- Checked: lint, typecheck and build pass; the 9 new tests pass.

**Step 6 (browser check, 2026-11-11, dev server on port 3000, local test account made through localhost sign-up)**

- Signed in, `/dashboard` landed on `/today` (page title "Today | Jobmigo"); the sidebar lists Today, Jobs, Profile and Settings with the current page marked `aria-current`, and no "Soon" item remains. Sign-up lands on `/onboarding` as before.
- Settings at 1440px shows the name and email as text, a Sign out button that returns to `/sign-in` (the jobs API answers 401 afterwards), and the Later group with no buttons.
- Workspace: the Open link on a Jobs row (44px) opens `/jobs/<id>` with the title, company and location; ArrowRight, End, wrap-around and Home move selection and focus, and ArrowDown changes nothing; the Jobs nav item stays marked. A made-up id and a malformed id both show "We could not find this job" (the two console errors are the expected 404s).
- 390px (Today, Settings, Jobs, workspace): the bar is fixed at the bottom (69px high, tabs 56px), the top bar keeps the logo and Sign out, `scrollWidth` equals 390 on all four pages, and no app control is under 44px except the two on Jobs below. The page has 96px of bottom padding so the last card clears the bar.
- Not checked: the failed-with-retry state of Today, Settings and the workspace (no way to make the server fail from here; it is the same pattern as the built Today page), and a real phone.

**Differences from the boards and known issues**

- Breakpoint: the bottom bar starts at `md` (768px); the boards use 720px.
- Jobs page (built, untouched here): the Saved and Dismissed view buttons are 40px high at 390px, under the 44px target the boards and spec ask for. Out of scope for 33b; fix with the stage views.
- Dev only: the TanStack devtools launcher floats over the Settings tab at 390px. It does not exist in a production build.
- Settings, Jobs and workspace differences listed above are unchanged. The workspace tabs use the pill style of the boards but show no status text yet.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":14186,"specSha256":"9431d1b7845ef97400e90ceacdf67c203e2820a54aea72a9968419d9a2064b86","branch":"refs/heads/feature/app-shell-and-navigation","head":"302ac7a0eab62d223daf6a5de5ec6023aef60841","baseRef":"refs/heads/main","baseCommit":"302ac7a0eab62d223daf6a5de5ec6023aef60841","sourceTree":"8af9c5e04cdf8fb64af54080166a9d561fc84073","landing":"local-merge","absentOptional":[]} -->
