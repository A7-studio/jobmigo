# Fix: Slow AI calls time out in the web server

**Type:** Fix
**Status:** verified
**Branch:** fix/slow-ai-calls

## The problem

First real run with the founder's model (free OpenRouter models): the fit check worked (22 s) but
writing a kit showed "Something went wrong". The CV took 24.6 s and the proposal about as long, one
after the other, and the web server gives the engine only 30 s, so the web call was cancelled while
the engine was still working.

## The fix

1. **Timeout.** `forward` takes an optional `timeoutMs`; the fit check, the screen and the kit write
   wait up to four minutes (`AI_TIMEOUT_MS`).
2. **Parallel writing.** The documents of a kit do not depend on each other, so the engine writes them
   with `asyncio.gather`: a kit takes as long as its slowest document. Nothing is saved unless every
   document worked, and the first failure is raised. Tests: a barrier that only opens when both model
   calls are in flight together, and a failing document saves nothing.

## Notes

- No independent review was run, at the founder's request to finish quickly.
- Verify: engine 916 passed, 11 skipped; ruff, format and mypy pass; web lint, typecheck and build
  pass; web tests 261 passed, 1 skipped.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":1224,"specSha256":"25539d66fc17a25debb39a9a9c8968f44b77a891291860eb8bd0d90feee1f323","branch":"refs/heads/fix/slow-ai-calls","head":"6ca70cb8a268a1949a43fb3b7a6176725a29a724","baseRef":"refs/heads/main","baseCommit":"6ca70cb8a268a1949a43fb3b7a6176725a29a724","sourceTree":"f73b1cb3fbe6b6b923ab3b6ea2cad23a394948d6","landing":"local-merge","absentOptional":[]} -->

## Independent review

Not run for this fix, at the founder's request.
