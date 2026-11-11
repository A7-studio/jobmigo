# Feature: Fit step in the job workspace

**From build-plan:** feature 8c
**Build attempt:** 1
**Status:** verified
**Branch:** feature/8c-fit-step

## Goal

The Fit tab of `/jobs/$jobId` shows the saved evaluation for one track, from the approved
board in `blueprint/reference/job.dc.html`: the band and the main gap first, the practical
checks, and every requirement with its quote and evidence one click away. It covers the
states not started, working, ready, stale, failed with retry, and no tracks.

## In scope

- `web/src/lib/fit-view.ts`: pure labels and rules (status words, check rows, calm error copy,
  which track to show first).
- `web/src/components/jobs/fit-step.tsx`: loads tracks and kept evaluations, runs
  `evaluateJob` on request, shows the states above. A track picker appears when there is more
  than one track.
- `job-workspace.tsx`: the Fit panel renders `FitStep`; the other three steps stay placeholders.
- Tests for `fit-view`; type, lint and build pass.

## Out of scope

Engine changes, the screen result in the UI, other steps, "Prepare application", the golden set.

## Rules

- No score or percentage. The band words are Strong, Good, Stretch and Weak fit.
- Posting quotes, notes and evidence are shown as text only, never as markup. AI notes are
  labelled as AI output. Importance is shown as the AI's guess ("Important", "Nice to have").
- Evaluating calls a model: it runs only when the person presses a button, never on page load.
- No error code or raw message is shown.

## Build steps

- [x] 1. `fit-view.ts` and `web/tests/fit-view.test.ts`.
- [x] 2. `fit-step.tsx` and the workspace wiring.
- [x] 3. Verify: web lint, typecheck, tests, build; browser check if the dev server is up.

## Notes for the AI

Reuse `Problem`, `BTN`, `BTN_PRIMARY` from `#/components/cv/parts`, `listTracks`, and
`bandLabel`. Tokens are the ones already used in `job-workspace.tsx`.

## Step notes

- Verify: web lint, typecheck and build pass; web tests 217 passed, 1 skipped (8 new in
  `fit-view.test.ts`). Engine untouched.
- Browser check at phone width (451 px) on the local dev server with a throwaway test account
  and one test job: the Fit tab shows the "Add a track to check fit" state. The engine had to
  be restarted and migrations 0011 and 0012 applied first (the running engine predated the 8b
  routes; the tab then correctly showed its "no longer there" message for the 404).
- Not seen in a browser: not started, working, ready, stale and failed states. The account has no
  track and no confirmed profile facts, and no `AI_STRONG_MODEL` is set. They are covered by
  `fit-view` tests only. Do this with a real track and a model before relying on the screen.
- No independent review: the config asks for one only for sensitive work, and this adds no new
  data flow (the evaluate call already existed from 8b).


<!-- blueprint:completion {"schemaVersion":2,"specBytes":2853,"specSha256":"301090ae51cb7926e941f5d91b8cbbc9f80f9abd86b5258ad4c62542e5577fcf","branch":"refs/heads/feature/8c-fit-step","head":"cf20ba8d87fcc5b5544a983a14e66aa003537370","baseRef":"refs/heads/main","baseCommit":"cf20ba8d87fcc5b5544a983a14e66aa003537370","sourceTree":"c1ee390fada19a331479b55f6a0eec90bf9573fb","landing":"local-merge","absentOptional":[]} -->
