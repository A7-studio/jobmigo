# Fix: Hero overflow at phone width

**Type:** Fix
**Status:** verified
**Branch:** fix/hero-overflow-at-phone-width

## The problem

At a 375px viewport the home page scrolls sideways by about 2px. The hero's
decorative visual (`web/src/components/home/Hero.tsx`, the `aria-hidden` block
around line 48) is `min-w-[300px]` and holds a fixed 380px circle, centred with
negative margins. On a phone the column is narrower than the circle, so the
circle extends past the page edge and widens the document.

## The fix

Stop the circle exceeding its column instead of hiding the overflow:

- Size the circle as `w-[min(380px,100%)] aspect-square`, centred, in place of the fixed
  `size-[380px]` and negative margins, so it shrinks on narrow screens and stays 380px
  from tablet width up.
- Leave the mascot, chips, copy and every other element as they are. No new
  dependency, config or wrapper unless the check shows the circle is not the only cause.
- If the page still overflows, find the next element that does (do not mask it with
  `overflow-x: hidden` on `body`).

## Build steps

- [x] 1. Resize the circle as above. Done when at 375px `document.documentElement.scrollWidth`
  equals `clientWidth`, the circle is fully visible and centred behind the mascot, and
  at 1280px the hero looks unchanged (380px circle).

## Verify

- `(cd web && npm run lint && npm run typecheck && npm run build && npm test) && (cd engine && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run --env-file ../.env pytest)`
- In the browser at 375px, 768px and 1280px: no horizontal scroll (check `scrollWidth` vs
  `clientWidth`), screenshot of the hero at 375px and 1280px.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":1687,"specSha256":"01cd27ad3cae8b366ca9bc37921ddd2b03d344f3d10e8c49a5ad57d26cb287b2","branch":"refs/heads/fix/hero-overflow-at-phone-width","head":"873b38721179f7cf38b5902bd5feb072951e458f","baseRef":"refs/heads/main","baseCommit":"873b38721179f7cf38b5902bd5feb072951e458f","sourceTree":"1146380a253f6d0d543ed40c9f8fdd9902e83708","landing":"local-merge","absentOptional":[]} -->
