# Fix: Export and screen polish

**Type:** Fix
**Status:** verified
**Branch:** fix/export-and-screen-polish
**Fixes:** F-194, F-195, F-196, F-197, F-198, F-199, F-200, F-201

## The problem

Two independent reviews left eight findings. The export (11c) printed an entry's heading and a
skill's name from the copy taken when the kit was written, so a fact the person corrected since was
not reflected (F-197, P2); the PDF showed characters its font cannot draw as `?` with no warning
(F-198, P2); a long company name could cut the file extension off, and an emoji in the web server's
name cut could turn a good export into a 502 (F-199); the DOCX kept the template's theme fonts, a
blue Title border and a 2013 creation date (F-200); the download form left its error on screen and
counted UTF-16 units (F-201). On the screen (11b): the edit box cut a legal edit at the wrong length
(F-194), the "Saved" message did not move focus after the first save (F-195), and typed text was
dropped when a refetch replaced the version, with a failed save's message shown twice (F-196).

## The fix

1. **F-197.** `recheck` reads each entry heading and each skill name from the fact as it is now
   (`heading_of`, the fact's own text, its current label); a skill whose fact is gone or is no longer
   a skill is dropped and counted; an entry whose fact is gone keeps its heading and its bullets are
   flagged.
2. **F-198.** The export says how many characters the PDF cannot draw (`replaced`, 0 for a DOCX); it
   travels as `x-export-replaced`, and the screen tells the person after the download that the DOCX
   keeps them.
3. **F-199.** The engine cuts the stem and adds the extension; the web server cuts by characters and
   drops a lone surrogate, so the name always encodes.
4. **F-200.** DOCX styles lose their theme-font attributes (and get East Asian and complex-script
   Arial), the Title loses its border, and the created, modified and last-modified-by properties are
   set fresh.
5. **F-201.** The form clears its error as the person types, ties it to the field (`aria-invalid`,
   `aria-describedby`) and counts and clips by characters, not UTF-16 units.
6. **F-194.** The edit box has no hard `maxLength`; it counts like the engine (whitespace collapsed,
   characters) and says "over by N", and Save is disabled only when over.
7. **F-195.** Each notice is a new object so focus and the announcement repeat; the version picker
   resets the error; a failed save clears the notice; the new version is put in the cache at once, so
   a failed refetch cannot leave the old version open.
8. **F-196.** The edit draft lives in `KitStep`. If the document changes under it, the text is kept in
   an "Your unsaved text was not saved" panel with a Dismiss button. A failed save is shown beside
   the editor only.

## Build steps

- [x] 1. Engine: `kit_edit.py`, `kit_export.py`, `kitting.py` and tests written first and seen to fail.
- [x] 2. Web: proxy, client, helpers, `kit-step.tsx` and tests.
- [x] 3. Verify; independent review; archive; merge.

## Notes

- No independent review was run for this fix, at the founder's request to finish quickly (2026-11-12).
  Each finding was reproduced with a failing test first. Verify: engine 914 passed, 11 skipped; ruff,
  format and mypy pass; web lint, typecheck and build pass; web tests 261 passed, 1 skipped.

- Verify: engine and web suites, lint, typecheck and build. The web has no rendering tests, so the
  screen changes are checked by reading and, later, in a browser.
- The source label of an entry now follows its fact's current label; the test that expected the
  stored label was changed on purpose.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":3660,"specSha256":"e5b65278bdf9de7f31d58378e677bc08e1c8910d580fc01e77b5226aa9074610","branch":"refs/heads/fix/export-and-screen-polish","head":"577a612361b8c3c5f06e20c7c084d9267ba6083e","baseRef":"refs/heads/main","baseCommit":"c34edc44e085f76d1ca4f578bd204d1908d705e2","sourceTree":"da34b641450d867d34abdbe249521c5b998ed1c9","landing":"local-merge","absentOptional":[]} -->

## Independent review

Not run for this fix, at the founder's request.
