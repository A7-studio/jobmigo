# Fix: Collapse the homepage nav into a menu on phones

**Type:** Fix
**Status:** verified
**Branch:** fix/collapse-the-homepage-nav-into-a-menu-on-phones

## The problem

Below 1024px the homepage header (`web/src/components/home/Nav.tsx`) is a wrapping row. At
375px the wordmark, three section links, "Sign in" and "Join the waitlist" take two to three
rows, about 130px, before the hero starts. A phone nav should collapse behind a menu button.

Design reference: the `Home` board in the design canvas
(https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q) shows the same wrapping row and has no
mobile menu state, so it does not decide this. The pattern below is proposed by this fix and
shown to the user for approval before the canvas is touched (a canvas update stays a separate,
explicitly approved step).

## The fix

On screens narrower than `lg` (1024px) the header becomes one row: wordmark on the left, then
the "Join the waitlist" pill button and a pill "Menu" button on the right. The Menu button
opens a panel directly under the header holding the four links (How it works, Features, Honest
by design, Sign in). From `lg` up nothing changes (the floating sticky pill nav stays).

Behaviour:
- A real `<button type="button">` with `aria-expanded`, `aria-controls` and a visible label that
  reads "Menu" when closed and "Close" when open; at least 44px tall; visible focus ring.
- Escape closes the panel and returns focus to the button; choosing a link closes it (the page
  scrolls to the section as today); a tap outside does not need special handling.
- Without JavaScript the four links must still be reachable: the server HTML renders the links
  visible, and the collapse applies only after hydration (the same no-JS-safe approach as the
  scroll reveals). Reduced motion: no slide animation is required, so there is nothing to
  disable beyond the global rule.
- Anchor targets keep clearing the header: on phones the header is in normal flow, so
  `scroll-margin-top` stays 1.5rem.

No new dependency; use React state in `Nav.tsx` (it becomes a client component only in the
sense it already is), the existing tokens and `rounded-full` pills. Do not touch the desktop
layout or other pages.

## Build steps

- [x] 1. **Mobile menu in `Nav.tsx`.** Add the Menu/Close button, the panel and the
  hydration-safe collapse. Done when: lint, typecheck and build pass; with JavaScript off the
  served HTML still contains all four links; at 375px the header is a single row (height under
  72px) with the wordmark, "Join the waitlist" and Menu; tapping Menu shows the four links,
  `aria-expanded` flips, Escape and choosing a link close it and Escape returns focus to the
  button; "How it works" lands on its section with the heading visible; there is no horizontal
  overflow at 375px; at 1280px the header is unchanged (sticky pill, no Menu button); at 768px
  the collapsed header is used.

## Verify

- `(cd web && npm run lint && npm run typecheck && npm run build && npm test) && (cd engine && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run --env-file ../.env pytest)`
- Browser at 375px, 768px and 1280px (the dev server is needed; ask the user to start it):
  header height, open and close by tap and by keyboard (Tab to the button, Enter, Escape),
  screenshots of the closed and open states, console free of new errors.

## Open questions

- Non-blocking: whether the `Home` canvas board should gain a mobile-nav state (decided after
  this is built and approved, as a separate canvas update).


<!-- blueprint:completion {"schemaVersion":2,"specBytes":3550,"specSha256":"866de6a25279f6c671b6b909f37bae6ddc55fd9b25b67fc2c482b11388ec2929","branch":"refs/heads/fix/collapse-the-homepage-nav-into-a-menu-on-phones","head":"4e2709f9a385aced8763926445030d6167f89572","baseRef":"refs/heads/main","baseCommit":"4e2709f9a385aced8763926445030d6167f89572","sourceTree":"c792a02e5ad1f182fb5660147e786936ec6a7228","landing":"local-merge","absentOptional":[]} -->


## Try it now

These are instructions for you to follow; they were not performed by you. Start the site with `npm run dev` in `web/`, then:

1. Open http://localhost:3000 in a window about 375px wide (or your phone's browser on the same network). The header is one row: the wordmark, "Join" (or "Join the waitlist" above 430px) and a Menu button.
2. Tap Menu. The four links appear in a panel and the button reads "Close". Press Escape (with a keyboard) or tap Close: the panel closes and focus returns to the button.
3. Open the menu again and tap "How it works": the panel closes and the page scrolls to that section with its heading in view.
4. Widen the window to 1024px or more: the Menu button disappears and the floating pill nav with the four inline links and "Join the waitlist" returns, staying at the top as you scroll.
