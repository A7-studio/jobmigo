# Feature: Application tracking

**From build-plan:** feature 12
**Status:** verified
**Branch:** feature/12-application-tracking

## What was built

- Migration `0016_job_tracking.py`: `job.stage` (saved, preparing, applied, interviewing, offer,
  closed; default saved), `outcome` (no_response, rejected, interview, offer; nullable), `applied_at`,
  `follow_up_on` (a date), `notes` (at most 4,000 characters) and `stage_changed_at`, each with checks.
- Engine: `JobPatch` takes `stage`, `outcome`, `followUpOn` and `notes` beside `status` and `kind`;
  `outcome`, `followUpOn` and `notes` can be sent as null to clear them. Moving to `applied` stamps
  `applied_at` once and never again; only a real stage change touches `stage_changed_at`. Notes keep
  line breaks and lose control characters. Ownership and validation as for every job change.
- Web: `trackJob`, `tracking-view.ts` (stage and outcome words, `followUpNote`, `appliedNote`,
  `countByStage`), `TrackStep` (the Track tab: stage, "Open the posting and apply" then "Did you
  apply?", follow-up date, outcome, notes), stage filters with counts on the Jobs list, and each row's
  stage and follow-up note.

## Left out, recorded as 12b in the plan

Interview stages (each interview's stage, date and notes) and the interviews of every application by
track; the board view comes later.

## Notes

- No independent review was run, at the founder's request to finish quickly.
- Verify: engine 937 passed, 11 skipped; ruff, format and mypy pass; web lint, typecheck and build pass;
  web tests 269 passed, 1 skipped. Not yet seen in a browser (needs migration `0016` and an engine restart).


<!-- blueprint:completion {"schemaVersion":2,"specBytes":1652,"specSha256":"ea3275fb401d9f6e11280e49da44736834e78ee024a6b1514e50a85a82660970","branch":"refs/heads/feature/12-application-tracking","head":"52327f3735262485997e18a78880d1f8737db9fa","baseRef":"refs/heads/main","baseCommit":"52327f3735262485997e18a78880d1f8737db9fa","sourceTree":"ede975de89d1fc449e2727340bba47f6aa1216c5","landing":"local-merge","absentOptional":[]} -->

## Independent review

Not run for this fix, at the founder's request.
