# Fix: Dates on a CV read like a typo

**Type:** Fix
**Status:** verified
**Branch:** fix/heading-dates

## The problem

The first real CV printed "(2026-05-2026-10)" after each role: a fact stores its span as
`start-end`, which reads as a typo on a CV.

## The fix

`heading_of` writes a span as a range, "(2026-05 – 2026-10)", "(2022 – 2024)" or "(2025-01 –
present)". Exports and the screen read headings from the facts as they are now, so a kit written
before this change shows the new form when exported. Tests cover each form and a heading without a span.

## Notes

- No independent review was run, at the founder's request to finish quickly.
- Verify: engine kit tests 151 passed; ruff, format and mypy pass.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":723,"specSha256":"21940b05c04b172d2900b80dcd5007189fcff3e94efcd9e366e0de9fcbe65b79","branch":"refs/heads/fix/heading-dates","head":"323dba1cdd8cfc443be6057283344471eda4e6b1","baseRef":"refs/heads/main","baseCommit":"323dba1cdd8cfc443be6057283344471eda4e6b1","sourceTree":"143063fd33feddd71337eeca837bf8afbc24e14b","landing":"local-merge","absentOptional":[]} -->

## Independent review

Not run for this fix, at the founder's request.
