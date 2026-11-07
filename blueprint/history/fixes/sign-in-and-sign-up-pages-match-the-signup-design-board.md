# Fix: Sign-in and sign-up pages match the Signup design board

**Type:** Fix
**Status:** verified
**Branch:** fix/sign-in-and-sign-up-pages-match-the-signup-design-board

## The problem

Feature 1 specified sign-in and sign-up "built from the design", but the built pages
(`web/src/components/AuthForm.tsx`, routes `/sign-in` and `/sign-up`) are one plain centred
card. The approved canvas board `Signup` is a split screen. Behaviour was tested in feature
1; the layout was never compared with the board, so the drift went unnoticed.

Design reference: https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q, board `Signup`
(version 27; the copy was corrected for honesty, so use that version's wording).

## The fix

Rebuild the presentation of both pages to the board, keeping all existing behaviour.

**Sign-up (`/sign-up`)**, left column on white: Migo wordmark linking home; heading "Let's make
job hunting feel lighter." (42px display); lead "Create your free account. It takes under a
minute."; the Google button (only when Google is configured, as today) with an "or use your
email" divider above the form (no divider when Google is off); fields with 48px inputs and 12px
radius; password hint "Use a phrase you will remember. Longer is stronger."; consent checkbox;
full-width pill button "Create my free account"; "No card needed. Already have an account?
Sign in". Right column on the accent-soft tint: Migo (110px, joyful variant with open mouth and
sparkles) beside a speech bubble ("Welcome! You are in good hands. I will keep this simple.");
a white "What happens next" card with three numbered steps (Upload your CV; Tell Migo what you
want; See your first evaluation: "Paste a job and see how it fits, with evidence."); three trust
lines with icons ("Your CV is private. Only you can see it." / "Nothing is ever sent without your
say-so." / "Export or delete your data whenever you like."). On narrow screens the right column
stacks below the form, as the board wraps.

**Sign-in (`/sign-in`)**: there is no separate board, so it reuses the same split layout with its
own copy: heading "Welcome back", lead "Sign in to pick up where you left off.", the existing
form, "New to Jobmigo? Create an account"; the right column keeps Migo with a bubble ("Welcome
back! Let's pick up where you left off.") and the three trust lines, without "What happens next".

**Deliberate differences from the board** (each stated, none hidden):
- The **Name** field stays above Email: Better Auth sign-up requires a name and the dashboard
  greets by it; the board omits it.
- The **"You picked Pro"** banner is not built: billing and plan selection do not exist yet.
- The **consent checkbox** links only the Privacy Policy (`/privacy` exists; no Terms page
  exists yet), reads "I agree to the Privacy Policy.", and must be ticked to sign up (inline
  error, labelled and tied with `aria-describedby`). Nothing new is stored; recording consent
  is a later decision. Add Terms to the line when a Terms page exists.
- The Google button stays conditional on configuration.

Must not break: validation and server error messages (invalid email, short password, duplicate
email, wrong password, network failure), focus moves to the first invalid field, the live error
region, redirect to `/dashboard`, the Google flow, and `queryClient.clear()` on success.
No new dependency; reuse `Wordmark`/`Migo` and the existing tokens; add only a small joyful
variant to `Migo`.

## Build steps

- [x] 1. **Shared split layout and sign-up.** Add `web/src/components/AuthShell.tsx` (left
  column slot plus the right panel, `mode`-dependent copy), a `joy` variant on `Migo`, and
  restyle sign-up in `AuthForm.tsx` with the consent checkbox. Done when: lint, typecheck and
  build pass; at 1440px the page matches the `Signup` board section by section (a side-by-side
  screenshot, with every difference listed) and at 375px the layout stacks with no horizontal
  overflow; an invalid email, a short password, an unticked checkbox, a duplicate email and a
  valid sign-up (lands on `/dashboard`) each behave correctly in the browser.
- [x] 2. **Sign-in on the same layout.** Apply the shell to `/sign-in` with its copy. Done when:
  lint, typecheck and build pass; at 1440px and 375px the page uses the shell with no overflow;
  a wrong password shows its message, a correct sign-in lands on `/dashboard`, and the
  Create-an-account link works.

## Verify

- `(cd web && npm run lint && npm run typecheck && npm run build && npm test) && (cd engine && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run --env-file ../.env pytest)`
- Side-by-side comparison with the board: open the artifact URL in the browser pane if it can
  show it; otherwise compare against the board markup values (sizes, colours, text) and say
  which was used. Tab through both pages (labels, focus ring, order) and check with
  `prefers-reduced-motion`. Browser checks need the dev server running (ask the user).

## Open questions

- None blocking. Non-blocking: whether to record consent (and add a Terms page) before real
  sign-ups open.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":5123,"specSha256":"6dd33a68d657059554de00a752c754b9dae19623403fba0e7ddb523efadd60f4","branch":"refs/heads/fix/sign-in-and-sign-up-pages-match-the-signup-design-board","head":"131348aa301ce611c4e134ea17e42f570bc8b527","baseRef":"refs/heads/main","baseCommit":"131348aa301ce611c4e134ea17e42f570bc8b527","sourceTree":"01ee9c3485bb7e8fa8e8352d82f7ec33e847eac0","landing":"local-merge","absentOptional":[]} -->


## Try it now

These are instructions for you to follow; they were not performed by you. Start the site with `npm run dev` in `web/`, then:

1. Open http://localhost:3000/sign-up in a desktop-width window. The page is a split screen: the form on the left, and on the right Migo with a speech bubble, a "What happens next" card and three trust lines. Compare it with the `Signup` board in the design canvas.
2. Press the button with empty fields: all four errors appear and focus moves to the Name field. Fill the fields but leave the Privacy Policy box unticked: the consent error appears and focus moves to the box.
3. Tick the box and sign up with a fresh email: you land on `/dashboard`. Sign out, then try the same email again: you are told the account already exists.
4. Open http://localhost:3000/sign-in: same layout with "Welcome back", no "What happens next" card. A wrong password shows the mismatch message; the right one lands on `/dashboard`; "Create an account" goes to `/sign-up`.
5. Narrow the window to about 375px: the right column stacks under the form and the page does not scroll sideways.
