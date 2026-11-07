# Fix: Pill-shaped call-to-action buttons

**Type:** Fix
**Status:** verified
**Branch:** fix/pill-shaped-call-to-action-buttons

## The problem

Call-to-action buttons use `rounded-md` (12px corners). The founder wants them pill-shaped
(fully rounded), in the style of modern marketing sites. The change is a design-token style
decision, not a bug, and it touches only the shape of buttons.

Buttons and button-styled links that carry the primary or secondary action today
(`web/src`):

- `components/home/Hero.tsx`: "Join the waitlist" and "See how it works" (lines 32, 38)
- `components/home/Nav.tsx`: the nav call-to-action (line 35)
- `components/WaitlistForm.tsx`: the submit button (line 166)
- `components/AuthForm.tsx`: the primary and secondary submit buttons (lines 204, 215)
- `components/MessagePage.tsx`: the shared button class (line 29)
- `routes/waitlist/confirm.tsx` and `routes/waitlist/unsubscribe.tsx`: the confirm and
  unsubscribe buttons (lines 80, 65)
- `routes/_app.tsx`: the sign-out button (line 80) and the call-to-action at line 108
- `routes/_app/dashboard.tsx`: the dashboard call-to-action (line 49)

## The fix

Change only the corner radius of those controls from `rounded-md` to `rounded-full`, keeping
their height (44px or 48px minimum), padding, colours, focus ring, hover and disabled states
and text exactly as they are.

What must not change:

- Text fields, selects and the consent checkbox keep `rounded-md`.
- Error and notice banners, loading skeletons, the sidebar navigation items and the small text
  link in the nav keep `rounded-md`.
- No new token, component or dependency: `rounded-full` is already available in Tailwind. If the
  same class string is repeated in many places, leave it as it is; this is a one-word change per
  control, and a shared button component is a separate piece of work.
- The 44px touch-target minimum and keyboard focus visibility stay as they are.

Out of scope: the Jobmigo Design artifact on claude.ai (it is outside this repository; update it
separately once the code shape is approved).

## Build steps

- [x] 1. Replace `rounded-md` with `rounded-full` on exactly the controls listed above, and no
  other element. Done when `grep -rn "rounded-full" web/src` shows only those controls plus any
  that already existed, every control still has its original `min-h-11` or `min-h-12`, and
  `npm run lint && npm run typecheck && npm run build && npm test` in `web/` passes.

## Verify

Start the dev server (`npm run dev` in `web/`) and look at `/` (the hero buttons, the nav button
and the waitlist submit), `/sign-in` (both buttons) and the waitlist confirm page. Each button
should be a pill with the same height, colours and focus ring as before; the inputs beside them
should still have the softer corners. Check keyboard focus on one button and that the layout does
not shift at phone width (about 400 px). I will take screenshots of those pages in the built-in
browser as evidence.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":2971,"specSha256":"becd6568ace5fc1e32cbcc4f333350c4988bdf8e075b213dd282e568e647e373","branch":"refs/heads/fix/pill-shaped-call-to-action-buttons","head":"0eeb852c7a5e821dff9d781a55f8daf5790f2aad","baseRef":"refs/heads/main","baseCommit":"0eeb852c7a5e821dff9d781a55f8daf5790f2aad","sourceTree":"18543fdba41c7bc944a972e5727cbefd6a42d001","landing":"local-merge","absentOptional":[]} -->
