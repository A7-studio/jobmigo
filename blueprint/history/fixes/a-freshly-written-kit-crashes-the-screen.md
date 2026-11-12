# Fix: A freshly written kit crashes the screen

**Type:** Fix
**Status:** verified
**Branch:** fix/kit-edited-default

## The problem

The first kit written by a real model saved fine, but the CV and letter screen crashed with
"Cannot read properties of undefined (reading 'length')". The fact check of a kit written by the
engine has no `edited` list (only a rechecked or edited one has), and the screen read
`factCheck.edited.length`. The test kit used for the earlier browser check had the list, which hid it.

## The fix

The engine now writes `edited: []` in every fact check, and the type makes `edited` optional so the
screen counts it safely (`?.length ?? 0`) for kits saved before. A test checks all three document
shapes.

## Notes

- No independent review was run, at the founder's request to finish quickly.
- Verify: engine kit tests 150 passed; ruff, format, mypy pass; web lint, typecheck, build pass; web
  tests 261 passed, 1 skipped.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":953,"specSha256":"bb4e07418e61e1fe7cb79bcf19421be421881631f429b636c02f03f8fdc34477","branch":"refs/heads/fix/kit-edited-default","head":"f5636b53c5862d08b13b46107c3a484eaa4bb8f7","baseRef":"refs/heads/main","baseCommit":"f5636b53c5862d08b13b46107c3a484eaa4bb8f7","sourceTree":"2a122c0901d6439b77f8cb78502f2882504befed","landing":"local-merge","absentOptional":[]} -->

## Independent review

Not run for this fix, at the founder's request.
