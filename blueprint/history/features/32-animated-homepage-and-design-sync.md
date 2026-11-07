# Feature: Animated homepage and design sync

**From build-plan:** feature 32
**Build attempt:** 1
**Status:** verified
**Branch:** feature/animated-homepage-and-design-sync

## Goal

Make the public homepage livelier and easier to understand in ten seconds: a scripted
"paste a job" demo in the hero, scroll reveals, a sticky pill nav, and small Migo
reactions, all honest and all switched off for visitors who prefer reduced motion. Then
bring the design canvas (the "Jobmigo Design" artifact) back in line with what is built:
pill buttons, the new homepage, and the honest-copy fixes. The canvas is published only
with the user's explicit approval.

## Design reference

- Canvas: https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q (boards `Home`, `Signup`,
  `Onboarding`, `Welcome`, `Main`; all 24 boards for the button radius).
- Tokens: `web/src/styles.css` (ported from `prototypes/theme.css`). Existing motion
  classes (`migo`, `floaty`, `pop`, `rise`) and keyframes are reused.
- The reachresume.com homepage was only used as a loose inspiration for the *kind* of
  motion (floating cards, scroll reveals). Copy nothing from it: no layout, text, assets
  or claims.

## In scope

Homepage (web, code):
- **Hero demo:** a staged preview for a clearly labelled **sample job**: the job card,
  a few honest checks (live, posted date, salary listed), the evidence count climbing from
  0 to "6 of 7 must-haves evidenced" with the band "Strong fit" and one named gap, then
  three tailored CV lines with fact-check tags (Verified, Reworded, Confirm it). A visible
  "Preview, sample job" label and a **Replay** button. Migo nods once when the band lands.
- **Floating cards:** the existing preview chips enter with staggered `pop` and keep a
  gentle `floaty`.
- **Scroll reveals:** a small `Reveal` wrapper (IntersectionObserver, no library) for the
  journey steps (staggered), the feature sections, and the honesty section.
- **Sticky pill nav:** the nav becomes a floating, pill-shaped bar that sticks at the top
  from the `lg` breakpoint (1024px) up; on phones it stays in normal flow (it wraps to two rows
  there). Anchor targets must not hide under it (`scroll-margin-top`).
- **Reduced motion and no JS:** all content is present and visible in the server-rendered
  HTML; reveals and the demo only animate when motion is allowed. Under
  `prefers-reduced-motion` the demo shows its final frame and nothing is hidden.

Design canvas (published artifact):
- **Button radius:** pill-shaped call-to-action buttons (the shared `.btn` class) on all
  boards, matching the built app. Chips, icon buttons, inputs and option cards stay as
  they are.
- **Home:** the new hero (honest headline and intro copy as built, waitlist call to
  action, the sample-job demo as a static final frame labelled Preview).
- **Honest-copy fixes** on `Home`, `Signup`, `Onboarding`, `Welcome` and `Main`: remove
  outcome promises ("Get the interview", "We get you to the interview. You ace it."),
  "Nothing is sent anywhere" (the CV text is processed by an AI model), and "verified jobs,
  ranked with evidence, straight away". **Onboarding step 4** becomes "first evaluation"
  (paste a job and see an evidence-based evaluation), matching the plan.
- The exact change list is shown to the user and approved before anything is edited or
  published.

## Out of scope

- A real evaluation behind the demo (feature 8) and any network call from the homepage.
- A progress ring, XP, streaks or other gamified widgets on the homepage (feature 20).
- Layout changes to sign-up, sign-in, onboarding or the dashboard in the code (those
  differences between canvas and code belong to features 1, 19 and 9); only the canvas
  copy and button radius change here.
- Changes to waitlist behaviour, auth, the engine, the database or deploy files.
- New dependencies (animation, icon or state libraries).
- Switching the call to action from "Join the waitlist" to "Get started free" (a launch
  decision).

## Build loop

`workflow.stepReview: feature`, so steps run to the end and one review packet follows;
`workflow.checkpointCommits: disabled`, so `/complete` makes the single commit. Run the
narrow check per step; run the full Verify once at the end. The canvas publish is the
only external side effect: it happens in step 6 behind its own approval, before final
verification, and the independent review gate follows `qualityGates.regular`.

## Build steps

- [x] 1. **Motion foundation.** In `web/src/styles.css` add the keyframes and helpers the
  later steps need (a `nod` keyframe, a stagger delay via a CSS variable, a hidden-until-
  revealed state that applies only after hydration and only when motion is allowed) and
  raise `[id]` `scroll-margin-top` to clear the sticky nav. Add `web/src/components/home/
  Reveal.tsx`: wraps children, adds the revealed class once the element enters the viewport
  (IntersectionObserver, observer disconnected after first reveal, no-op when the API or
  motion is unavailable). Make `Nav.tsx` sticky and pill-shaped from `lg` up (translucent
  surface, border, `rounded-full`, shadow), unchanged on phones. Done when: lint,
  typecheck and build pass; the served HTML contains all homepage text with JS disabled;
  in the browser at 1280px the nav stays at the top while scrolling and at 375px it scrolls
  away normally with no horizontal overflow (`scrollWidth` equals `clientWidth`); clicking
  "How it works" lands with the section heading visible below the nav.
- [x] 2. **Hero demo.** Add `web/src/components/home/HeroDemo.tsx` and use it in `Hero.tsx`
  in place of the decorative chips (keep the circle and Migo and the width-safe circle
  from the last fix). Content: sample job card, three checks, evidence count animating
  0 to 6 of 7 (a small client effect that starts after mount and sets the final value
  immediately when motion is reduced; the server renders the final value), "Strong fit"
  band, one gap row ("Native iOS (Swift): nothing in your profile yet"), three CV lines
  with tags. A "Preview, sample job" label and the note "Sample only. Jobmigo is in early
  access." are always visible. A `Replay` button (real `<button>`, visible focus, accessible
  name) restarts the sequence by remounting. No percentage anywhere. Done when: lint,
  typecheck and build pass; in the browser the sequence plays once on load and again on
  Replay (keyboard Enter and Space); with reduced motion emulated the final frame shows at
  once; at 375px, 768px and 1280px there is no horizontal overflow and nothing overlaps
  the headline or buttons; screen-reader text is present in order (read via `read_page`).
- [x] 3. **Reveals and Migo moments.** Wrap the journey list (staggered steps), each
  `FeatureSection` in `Feature.tsx` (via `Sections.tsx` as needed), `AiSteps`, and `Honest`
  with `Reveal`; give the hero preview chips staggered `pop`; make Migo nod once when the
  demo band appears. Done when: lint, typecheck and build pass; at 1280px and 375px the
  sections below the fold reveal as they scroll into view and none stays hidden when the
  page is loaded already scrolled (reload mid-page and with a `#how` link); with reduced
  motion nothing is hidden or animated; no console errors.
- [x] 4. **Canvas audit and change list (read-only).** Read the boards named in scope and
  every board's `.btn` rule. Produce the exact change list: per board the old text and new
  text, and the button radius change. Apply the honest-copy rules (no outcome promises, no
  percentage fit, no claim that nothing is sent, no promise of a shortlist or a result).
  Show it to the user in chat. Done when: the list is shown and the user has approved it,
  or has given changes; nothing is edited or published yet.
- [x] 5. **Prepare the canvas edits locally.** Copy the changed boards to a folder in the
  scratchpad at `project/<name>` paths and apply the approved list there (edit only the
  approved lines, keep every other key and file). Done when: a diff of each changed board
  against the published copy matches the approved list exactly and nothing else.
- [x] 6. **Publish the canvas (explicit approval).** Show the user the final diff summary
  and the target (`https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q`, a new version of
  the same artifact) and wait for a clear yes. Then publish only the changed board files
  with the artifact's `root` and `files`; follow any refusal by re-reading the named file.
  Done when: the publish succeeds, a read-back of `Home` and `Onboarding` shows the new
  copy and no "Get the interview" or "Nothing is sent anywhere" text remains in the five
  boards, and the user has been told the link. If the user declines, stop and revise this
  step with them before `/complete`.

## Files / areas

- `web/src/styles.css`, `web/src/components/home/{Nav,Hero,Journey,AiSteps,Honest,Feature,
  Sections}.tsx`, new `web/src/components/home/{Reveal,HeroDemo}.tsx`, `web/src/routes/
  index.tsx` only if wiring needs it.
- Design canvas files `project/*.dc.html` (published artifact, not in this repository).
- No schema, server function, engine, deploy or dependency changes.

## Data / contracts

- All demo text is a fixed sample in the component; it carries no user data and makes no
  request. No percentages: the demo shows the evidence count and a fit band only.
- Copy rules stay as in the homepage: future tense for unbuilt features, no promise of an
  interview or job, "Preview" and "sample" visible next to every mock result.
- Accessibility: every text in the demo is real DOM text; animation never hides content
  from assistive tech; the Replay control is keyboard operable; contrast stays at the
  existing tokens (text 4.5:1).
- Reveals must degrade: no JS or no IntersectionObserver means everything is visible.

## Testing

- No logic tests: this is presentational and the web Vitest environment is Node-only. The
  evidence is the full Verify (lint, typecheck, build, existing 133 web tests, engine
  checks) plus browser evidence for steps 1 to 3 at 375px, 768px and 1280px, with reduced
  motion emulated once, and console and network checks (no failed requests, no errors).
- Baseline observed while specifying: web lint, typecheck and build clean, 133 tests
  passed and 2 skipped (12 files passed, 2 skipped); engine Ruff, format, mypy clean, 33
  tests passed.
- Canvas: the diff against the published copy is the check; no rendered screenshot of the
  canvas is claimed unless one is taken.

## Notes for the AI

- The plan line says "fit score counting up". Counting a score or percentage would
  contradict "fit is a band, never a percentage", so the demo counts evidenced must-haves
  and shows the band. Suggest rewording the plan line later (user-owned; do not edit it).
- I earlier said the built homepage lacked the discovery, evaluation and fact-check
  mockups. That was wrong: `Sections.tsx` already has them. The remaining homepage
  differences from the canvas are copy, the hero visual and button radius.
- Keep the homepage heading order and landmarks; the sticky nav is the same `<header>`.
- Do not start a dev server yourself; ask the user to run `npm run dev` in `web/` for the
  browser checks. Do not publish the canvas without a fresh explicit yes in chat.
- Decision recorded: the canvas Home shows the waitlist call to action to match the built
  page; the launch-time switch is a later change.

## Open questions

- None blocking. Non-blocking: reword the plan line's "fit score counting up" to
  "evidence count climbing" at the next plan edit.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":11576,"specSha256":"b254926694164fc2d0bf207353a98448bf61c965598ca6083c4e92f0880685ec","branch":"refs/heads/feature/animated-homepage-and-design-sync","head":"8f54e45a0bf413aeecc0e159c5f35f6914debd7e","baseRef":"refs/heads/main","baseCommit":"8f54e45a0bf413aeecc0e159c5f35f6914debd7e","sourceTree":"087fa9299251dd672f05398ba8604f9289fc42c5","landing":"local-merge","absentOptional":[]} -->


## Try it now

These are instructions for you to follow; they were not performed by you. Start the site with `npm run dev` in `web/`, then:

1. Open http://localhost:3000 in a desktop-width window. The hero card labelled "Preview · sample job" plays: three checks appear, the evidence count climbs from 0 to "6 of 7 must-haves evidenced", "Strong fit" lands and Migo nods, then a gap row and three CV lines with fact-check tags appear. Click **Replay** (or Tab to it and press Enter) to run it again.
2. Scroll down. The journey steps and each feature section fade up as they come into view. At 1024px or wider the nav is a floating pill that stays at the top; click "How it works" and the section heading lands below it.
3. Narrow the window to about 375px. The page does not scroll sideways, and the nav scrolls away with the page.
4. Turn on "Reduce motion" in your system settings and reload: the demo shows its final frame at once and nothing stays hidden.
5. Open the design canvas, https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q (version 27): buttons are pill-shaped, the Home board shows the new hero, and the Home, Signup, Onboarding and Welcome copy matches the honest wording.
