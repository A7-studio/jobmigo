# Feature: Homepage and waitlist

**From build-plan:** feature 28a
**Build attempt:** 1
**Branch:** feature/homepage-and-waitlist
**Status:** verified

## Goal

Someone who sees the LinkedIn post lands on a Jobmigo homepage that explains the
promise honestly, joins the waitlist with their email and explicit consent, gets
a confirmation email, and can confirm or unsubscribe with one click. The founder
can see how many people signed up and from which source. Everything is built and
tested locally; going live (domain, server, DNS) is feature 28b.

## Design reference

Approved design canvas: https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q, page
"Public and onboarding", board "Homepage" (`Home.dc.html`). Tokens are already in
`web/src/styles.css`; fonts (Fredoka, Nunito) are already linked in the root route.
Keep the design's structure, mascot, copy rhythm and 44px controls. Adjustments
for launch honesty are listed in Notes for the AI.

## In scope

- **Homepage at `/`:** nav, hero, journey strip, AI-step cards, discover,
  evaluate, prepare, reachability and progress sections, four-step explainer,
  "honest by design", waitlist section, footer. Responsive, keyboard accessible,
  motion respects reduced-motion.
- **Waitlist:** email plus a required consent checkbox, validation, duplicate
  handling that never reveals whether an address is already on the list, a rate
  limit, a honeypot, double opt-in confirmation, one-click unsubscribe, a stored
  consent record, and an optional `source` taken from `?utm_source` or `?ref`.
- **Mail layer:** an `EmailProvider` interface with a Resend implementation (plain
  `fetch`, no SDK) and a console implementation used when no API key is set.
- **Pages:** `/waitlist/confirm`, `/waitlist/unsubscribe`, `/privacy`.
- **Sharing:** page title, description, Open Graph and Twitter tags, a favicon and
  an Open Graph image so the LinkedIn post renders a card.
- **Review findings carried over:** F-05 (owner-scoping helper must not allow
  overwriting `userId` or `id`) and F-06 (tests for the real auth wiring).

## Out of scope

- Buying the domain, the production build, server, Caddy, Cloudflare, backups
  (28b). A live send through Resend needs a verified domain; this feature is tested
  with a fake provider and the console provider.
- Payment of any kind. The founding-member note is text only and shows no price.
- Marketing newsletters, an admin view of the list, CSV export tooling, analytics
  scripts, a Terms page, Swahili copy.
- Closing public sign-up. `/sign-up` stays reachable but is not linked from the
  homepage.

## Build loop

`workflow.stepReview` is `feature`: build all steps in order, run the narrow check
for each, run the full gate once at the end, then present one review packet.
`workflow.checkpointCommits` is disabled; `/complete` makes the commit.

## Build steps

- [x] **1. Waitlist data, mail layer and service.**
  Add `zod`. Add the `waitlist_signup` table to `web/src/server/db/schema.ts` and
  generate its migration with `npm run db:generate`. Add `src/server/mail.ts`
  (`EmailProvider { send({ to, subject, html, text, headers }) }`, a Resend
  implementation posting to `https://api.resend.com/emails` with `RESEND_API_KEY`
  and `MAIL_FROM`, and a console implementation that is selected when the key is
  unset and `ENVIRONMENT` is `local`; with no key in any other environment the
  first send fails loudly). Add `src/server/rate-limit.ts` (in-memory
  fixed-window limiter with an injectable clock) and `src/server/waitlist.ts`
  (`joinWaitlist`, `confirmWaitlist`, `unsubscribeWaitlist`, email templates as
  functions returning html and text). Tokens are 32 random bytes, base64url, sent
  once and stored only as a SHA-256 hash.
  *Done when:* Vitest tests (real test database, fake provider, injected clock)
  show: a join creates a pending row and sends exactly one email whose links carry
  the token; the raw token is not in the database; email is trimmed and
  lowercased and rejected when invalid or over 254 characters; consent is
  required; `source` is limited to 64 characters of `[a-z0-9_.-]` and otherwise
  dropped; a repeat join of a pending address within 10 minutes sends nothing and
  returns the same result, after 10 minutes sends a new email with a new token
  that invalidates the old one, and stops after 5 emails; a confirmed address
  sends nothing; an unsubscribed address that joins again becomes pending with a
  new consent timestamp; confirm succeeds with a valid token within 7 days, fails
  when expired, unknown or unsubscribed, and is idempotent when already confirmed;
  unsubscribe works at any age, is idempotent and fails for an unknown token; a
  provider failure returns `unavailable` and does not block an immediate retry;
  the limiter blocks the sixth call in a window and recovers after it. `npm run
  build`, `npm run lint`, `npm run typecheck` and `npm test` pass.

- [x] **2. Server function and confirm and unsubscribe pages.**
  Add `joinWaitlist` as a POST server function in `src/lib/waitlist.functions.ts`:
  the zod input is `{ email, consent, source?, website? }` where `website` is the
  honeypot (a non-empty value returns `{ ok: true }` without storing or sending),
  the caller's IP comes from `cf-connecting-ip`, then the first `x-forwarded-for`
  entry, then `"unknown"`, and the limiter allows 5 joins per IP per 10 minutes.
  Add the routes `/waitlist/confirm?token=` (confirms on load, shows confirmed,
  already confirmed, or expired or invalid) and `/waitlist/unsubscribe?token=`
  (shows a page with an Unsubscribe button that calls a server function, so link
  prefetchers cannot unsubscribe anyone). Pages share the app styling, have a link
  back to `/`, and announce results in a live region.
  *Done when:* tests cover the server function (honeypot, rate limit, invalid
  input, stable result shape, IP extraction order); with the dev server running,
  a join with the console provider logs the confirm link, opening it shows the
  confirmed page and a second open shows already confirmed, the unsubscribe page
  unsubscribes only after the button is pressed, and a bad token shows the
  invalid state (live check, built-in browser, no external accounts; the confirm behaviour is superseded by step 8); build, lint,
  typecheck and tests pass.

- [x] **3. Homepage shell: sharing tags, nav, hero and journey.**
  Replace `src/routes/index.tsx` (no signed-in redirect and no session lookup on
  `/`). Add `src/components/home/` components for the nav (Migo logo, How it
  works, Features, Honest by design, Sign in, Join the waitlist button), the hero
  ("Skip the ghost pipeline. Get the interview.", primary button scrolls to
  `#waitlist`, secondary to `#how`), the hero preview card and the eight-step
  journey strip. Port the needed keyframes (bob, blink, rise) into
  `src/styles.css`. Add head metadata for `/`: title, description, canonical URL
  from `PUBLIC_URL`, Open Graph and Twitter card tags, `public/favicon.svg`
  (Migo) and `public/og.png` (1200 by 630, Migo and the tagline, generated from a
  local page with the built-in browser; if that cannot be produced, ship without
  the image and say so in the review packet).
  *Done when:* build, lint, typecheck and tests pass; in the browser the hero and
  journey render at 1280px and 390px with no horizontal scroll, the nav buttons
  scroll to their sections, focus is visible, the page has one `h1`, and the
  served HTML head contains the Open Graph tags (checked with curl).

- [x] **4. Homepage content sections.**
  Add presentational components for the AI-step cards, Discover and verify,
  Evaluate, Prepare, Get seen, Stay in motion, the four-step explainer and Honest
  by design, with the design's example cards labelled "Preview". Copy follows the
  launch-honesty rules in Notes for the AI. Fit and status are conveyed by text,
  not colour alone.
  *Done when:* build, lint, typecheck and tests pass; in the browser all sections
  render in order at 1280px and 390px, headings form a sensible outline, every
  example card is labelled "Preview", and no text claims a feature is available
  today that is not.

- [x] **5. Waitlist section, form and privacy page.**
  Add the waitlist section (`id="waitlist"`) with a labelled email field, a
  required consent checkbox (text: "Email me about Jobmigo early access and launch
  updates. I can unsubscribe at any time." linking to `/privacy`), a hidden
  honeypot field, and a Join the waitlist button with a loading state. Inline
  errors tie to fields with `aria-describedby`, form-level results go in an
  `aria-live` region, focus moves to the first error, and success replaces the form
  with "Check your inbox to confirm" (the same message for new and repeat
  addresses). Read `utm_source` or `ref` from the URL and send it as `source`. Add
  `/privacy` (what is collected: email, consent time, source; why; Resend as the
  email processor; kept until you unsubscribe, after which only the email is kept
  to honour the unsubscribe; how to ask for deletion via the contact email) and
  the footer (A7Studio, Privacy, Contact from `CONTACT_EMAIL`).
  *Done when:* build, lint, typecheck and tests pass; in the browser an invalid
  email, a missing consent, a rate-limited sixth join, and a success each show
  the right message; the confirmation link from the dev log confirms the
  address; the same address joining twice shows the same success message; the
  page works at 390px with no horizontal scroll and the controls are at least 44px.

- [x] **6. Review fixes F-05 and F-06.**
  Make `updateOwned` ignore `userId` and `id` in `values` (remove them before the
  update) and add a test that passing them leaves the row's owner and id
  unchanged. Extract the request-id middleware body to a function, the readiness
  and health handlers to functions, and add tests for the real wiring using
  `vi.mock` for `#/lib/auth`: `requireUser(headers)` with a session, without one,
  and with a suspended user; `requirePermission(headers, ...)`; `buildMe` through
  the `getMe` path; the request-id function keeping a supplied id and generating
  one otherwise; `/readyz` returning 503 with the stable shape when the database
  call fails.
  *Done when:* the new tests pass and fail when the corresponding fix is
  reverted; build, lint, typecheck and tests pass.

- [x] **7. Environment, docs and final gate.**
  Add `RESEND_API_KEY`, `MAIL_FROM`, `CONTACT_EMAIL` and `PUBLIC_URL` (defaults to
  `BETTER_AUTH_URL`) to `.env.example` and the compose file, document the waitlist
  commands in `AGENTS.md`, add the waitlist table and rules to
  `docs/database-design.md`, and note the mail layer in `docs/technical-design.md`.
  Mark F-05 and F-06 fixed in the findings ledger only after their checks pass.
  *Done when:* the `Verify` command from `AGENTS.md` passes and a fresh clone can
  follow `.env.example` to run the homepage and a console-provider waitlist join.

- [x] **8. Review repairs: F-11, F-12, F-13.**
  Repair the three P2 findings from the independent review, as a user-approved
  change to the earlier contracts:
  (F-12) `/waitlist/confirm?token=` no longer confirms on load. It shows a
  "Confirm my email" button; pressing it calls the confirm server function and
  shows the existing confirmed, already confirmed, expired and invalid results, so
  mail scanners and link previews cannot confirm anyone.
  (F-11) `clientIp` reads `cf-connecting-ip` only when `TRUST_PROXY_HEADERS` is
  `true` (set only behind Cloudflare and Caddy, 28b) and otherwise returns no IP
  and ignores `x-forwarded-for`. With a trusted IP the limit stays 5 joins per IP
  per 10 minutes; without one the per-IP limit is skipped. A global limit of 60
  joins per 10 minutes always applies. The limiter map is hard-capped at 10,000
  keys (expired keys are swept, then the oldest are dropped).
  (F-13) `joinWaitlist` writes the row, then returns `{ ok: true }` without waiting
  for the email; the send runs in the background, a failure is logged (error class
  only) and resets `token_sent_at` so the next attempt resends at once. The
  `unavailable` result is removed.
  *Done when:* Vitest tests show: the confirm page code path performs no
  confirmation on load (the loader only reads the token) and confirms only through
  the server function; `clientIp` ignores both headers when `TRUST_PROXY_HEADERS` is
  not `true` and returns `cf-connecting-ip` when it is; with no trusted IP many
  joins pass the per-IP stage and the global cap blocks the 61st; the per-IP limit
  still blocks the sixth join from one trusted IP; the limiter never holds more
  than its cap of keys; a join with a failing provider returns `{ ok: true }`,
  logs without the address, leaves the row resendable, and the next join sends;
  join result time does not depend on the provider (a provider that never resolves
  still lets the join return). In the browser, the confirm link shows the button,
  loading the link alone leaves the row `pending`, pressing it confirms, and a
  second press shows already confirmed. `npm run lint`, `typecheck`, `build` and
  `npm test` pass.

## Files / areas

- `web/src/routes/index.tsx` (replaced), `waitlist/confirm.tsx`,
  `waitlist/unsubscribe.tsx`, `privacy.tsx`.
- `web/src/components/home/` (new), `web/src/components/WaitlistForm.tsx` (new).
- `web/src/lib/waitlist.functions.ts` (new).
- `web/src/server/mail.ts`, `rate-limit.ts`, `waitlist.ts` (new);
  `db/schema.ts` and `web/drizzle/` (new migration); `ownership.ts`,
  `identity.ts`, `permissions.ts`, `src/start.ts` (F-05 and F-06 extraction).
- `web/public/favicon.svg`, `web/public/og.png` (new); `web/src/styles.css`.
- `web/tests/` (new and extended), `.env.example`, `docker-compose.yml`,
  `AGENTS.md`, `docs/database-design.md`, `docs/technical-design.md`.

## Data / contracts

- **`waitlist_signup`:** `id` uuid pk (`gen_random_uuid()`), `email` text unique not
  null (lowercase, at most 254 characters), `status` text not null default
  `pending` with check (`pending`, `confirmed`, `unsubscribed`), `consent_text_version`
  text not null (`waitlist-v1`), `consented_at` timestamptz not null, `source` text
  null (at most 64 characters), `token_hash` text not null (SHA-256 hex),
  `token_sent_at` timestamptz not null, `emails_sent` integer not null default 1,
  `confirmed_at` null, `unsubscribed_at` null, `created_at`, `updated_at`.
  No IP address is stored. Unsubscribed rows are kept (email only needed) so an
  unsubscribe is honoured.
- **Join result:** `{ ok: true }` for new, repeat, confirmed and honeypot cases
  alike; otherwise `{ ok: false, code, message }` with `code` one of
  `invalid_email`, `consent_required`, `rate_limited` (step 8 removes `unavailable`).
- **Links:** `PUBLIC_URL/waitlist/confirm?token=<raw>` and
  `PUBLIC_URL/waitlist/unsubscribe?token=<raw>`. The unsubscribe link works at any
  age. The confirm link is valid 7 days after the latest email. Emails carry a
  `List-Unsubscribe` header with the unsubscribe URL.
- **Trust boundary:** all input is untrusted and validated with zod; the IP header
  is only trusted behind Cloudflare and Caddy (28b) and is used only for rate
  limiting; tokens never appear in logs outside the local console provider; log
  lines contain no email address; user text is never rendered as HTML.
- **Env:** `RESEND_API_KEY`, `MAIL_FROM`, `CONTACT_EMAIL`, `PUBLIC_URL`, `TRUST_PROXY_HEADERS` (step 8).

## Testing

Vitest against the real `jobmigo_test` database with a fake `EmailProvider` and an
injected clock; commands in `web/`: `npm test`, `npm run typecheck`, `npm run
lint`, `npm run build`. Live checks (steps 2, 3, 5) use the dev server, curl and
the built-in browser with the console provider and local test addresses only. No
live Resend send and no browser test harness is claimed.

## Notes for the AI

- **Launch honesty:** automatic job discovery and alerts are premium features built
  later. Write product claims about discovery, alerts, tailored CVs, the
  reachability check and quests in future or "coming" wording, keep the
  "AI proposes, you decide" principles, and use the design's example cards only
  with a "Preview" label. The primary buttons say "Join the waitlist". Remove
  "Get started free". The waitlist note reads "Early members get founding-member
  pricing." with no price (the design's placeholder is replaced).
- Port visuals from `Home.dc.html` (read it with the Artifact tool, path
  `project/Home.dc.html`); do not copy its inline styles, use Tailwind and the
  tokens, with a short comment only where a hard-coded value is unavoidable.
- Check installed package types for TanStack Start head metadata and server
  function validators before relying on a signature.
- Review ledger items F-07 to F-10 are not in scope here; do not widen the fix.
- Open decisions for the founder before 28b, not blocking this build:
  `CONTACT_EMAIL` and `MAIL_FROM` addresses (need the domain and Cloudflare Email
  Routing), and a legal read of the privacy notice before launch.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":17082,"specSha256":"8e492cd3068505edd323ae141a40d78889b1cae248e227637250a4db6478fe0c","branch":"refs/heads/feature/homepage-and-waitlist","head":"28b4397b275b3cadf0a026eb823b60375cb818e3","baseRef":"refs/heads/main","baseCommit":"16a65b2e0a7fdb052bca4d35534e885c94c203bc","sourceTree":"2599818dc5261854b40ea8ae0940009fc3f3e1e0","landing":"local-merge","absentOptional":[]} -->

## Findings

### 28a/F-05 [P2] closed - `updateOwned` lets the caller overwrite `userId` and `id`

**File:** web/src/server/ownership.ts:53
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** `values` is `Partial<T['$inferInsert']>`, which includes `userId` and `id`. A later handler that passes a parsed request body straight through (the usual shape) lets a client reassign a row to another user or change its key, defeating the "client never supplies a user id" boundary the helper exists to enforce. No caller exists yet and no test covers it.
**Suggested fix:** Type `values` as `Omit<Partial<T['$inferInsert']>, 'id' | 'userId'>` and strip those keys at runtime; add a test that `userId` in `values` is ignored or rejected. Nothing is lost.
**Resolution:** Feature 28a: `updateOwned` removes `id` and `userId` from the values before updating; a test passes both and shows the owner and id unchanged, and fails when the fix is reverted.
Re-examined 2026-11-07 by independent review (a3dfe45): `withoutOwnership` in `ownership.ts:15-24` strips `id` and `userId` before `.set()`, `tests/wiring.test.ts:139` asserts owner and id unchanged and would fail on revert; no new defect. Closed.

### 28a/F-12 [P2] closed - Confirmation happens on a GET page load, so mail scanners and prefetchers can confirm for the user

**File:** web/src/routes/waitlist/confirm.tsx:11
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** The route loader calls `confirmWaitlistFn` on load, so any security gateway, link previewer or antivirus that fetches the emailed URL (many do, and run the page's server rendering) marks the address `confirmed` with no human action. That defeats the point of double opt-in and the stored consent record, and confirms third-party addresses typed in by an attacker. The unsubscribe page already uses a button for exactly this reason; the spec asked for confirm-on-load, so this is a design weakness rather than a deviation.
**Suggested fix:** Mirror the unsubscribe page: the confirm URL shows a "Confirm my email" button that calls the server function. This needs a user decision because it changes the spec'd one-click behaviour.
**Resolution:** Step 8: the confirm page no longer confirms on load; a button calls the server function. Checked in a browser (loading leaves the row pending, pressing confirms) and a source test guards against a loader.
Re-examined 2026-11-07 by independent review (28b4397): `confirm.tsx` has no loader or effect, the only `confirmWaitlistFn` call is inside the button `onClick`, the missing-token case starts in `invalid`, and server rendering leaves the row pending. The original defect is gone and the repair added no security defect; the page's focus and live-region behaviour and the weak source-regex test are tracked separately as F-20 and F-22. Closed.

### 28a/F-13 [P2] closed - Join response time reveals whether an address is already on the list

**File:** web/src/server/waitlist.ts:171
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** The spec says duplicate handling never reveals whether an address is already on the list. The body is identical, but a new, unsubscribed or resendable address awaits `mail.send` (a network call to Resend, hundreds of milliseconds) while a confirmed or recently-pending address returns after two database queries. A caller can tell the difference by timing, and can probe addresses at the rate limit. A send failure also returns `unavailable` only on the send paths, which is a second oracle when the provider is down or unconfigured (`UnconfiguredProvider` in any non-local environment rejects every new address but not existing ones).
**Suggested fix:** Return `{ ok: true }` before the send completes (queue it and log failures) so every path has the same cost, or accept and document the residual leak. Dropping the `unavailable` code would lose the retry message; keep it only if the leak is accepted.
**Resolution:** Step 8: `joinWaitlist` returns `{ ok: true }` after the database write and sends the email in the background (failures logged without the address and made resendable); the `unavailable` result is removed. A test shows the join returns while the provider is still pending.
Re-examined 2026-11-07 by independent review (28b4397): `joinWaitlist` returns `{ ok: true }` right after the database write on every path, the send is detached through `track`, the `unavailable` code and its UI branch are gone (no references remain), and `sendConfirmation` catches provider errors, logs only the error name and resets `tokenSentAt` with a `.catch` so no unhandled rejection comes from it. The network-latency and provider-down oracles are removed; what remains is a difference of one or two database round trips between paths (milliseconds, below the noise of a rate-limited public endpoint). Closed; the lost-send edge cases are tracked as F-21.

## Independent review

**Status:** passed
**Target commit:** 28b4397b275b3cadf0a026eb823b60375cb818e3
**Base commit:** 16a65b2e0a7fdb052bca4d35534e885c94c203bc
**Base ref:** main
**Spec hash:** 8e492cd3068505edd323ae141a40d78889b1cae248e227637250a4db6478fe0c
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-07T08:33:31Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-07T08:50:00Z
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

- `git rev-parse HEAD`, `git merge-base main HEAD`, `shasum -a 256 blueprint/context/current-feature.md`: pass (HEAD 28b4397b, merge base 16a65b2e, spec hash matches, only review.md and findings.md dirty)
- `npm run lint` (web): pass
- `npm run typecheck` (web): pass
- `npm test` (web): pass (7 files, 71 tests)
- `npm run build` (web): pass

## Evidence

- Read the full `16a65b2..28b4397` delta for the waitlist service, rate limiter, join API, mail providers, confirm and unsubscribe routes, form, schema and migration, env and compose changes, and the waitlist tests, against the active spec.
- F-12 and F-13 re-examined against the new code and closed: `confirm.tsx` has no loader and only the button calls the server function; `joinWaitlist` returns after the database write and sends in a tracked background task with the `unavailable` result removed.
- F-11 reopened: `waitlist-api.ts` spends a global token before the per-IP check, so one over-limit client can exhaust the global cap and lock everyone out.
- New findings F-20 (confirm page focus and live region), F-21 (lost background sends, unwired flush), F-22 (tests that no longer prove their claims).

## Findings

- F-11 (P2, open), F-12 (closed), F-13 (closed), F-20, F-21, F-22 (P3, open). Earlier F-04 to F-10 and F-14 to F-19 are unchanged by this diff. No P0 or P1 finding is open or fixed.

## Remaining risk

- F-11 (P2) should be repaired before the public launch: reorder the limiters so a rate-limited address cannot spend the global budget.
- Background sends are not flushed on shutdown and failures are only logged (F-21); delivery was not tested against the real Resend API.
- `TRUST_PROXY_HEADERS=true` is safe only when the origin is reachable solely through Cloudflare and Caddy (feature 28b); that deployment was not reviewed.
- No browser or screen-reader pass was run on the confirm page.
