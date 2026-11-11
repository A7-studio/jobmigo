# Feature: PDF and DOCX export

**From build-plan:** feature 11c
**Build attempt:** 1
**Status:** verified
**Branch:** feature/11c-pdf-and-docx-export

## Goal

From a saved version of a kit document the person can download a plain, ATS-friendly PDF or DOCX:
the CV, the cover letter or proposal, or the answers. The file is made on demand and never stored.
Before building it the engine checks the document again against the person's current facts and
refuses while a statement still needs them.

## Decisions made with the founder (2026-11-11)

- reportlab (PDF) and python-docx (DOCX) are added to the engine (done: reportlab 5.1.0,
  python-docx 1.2.0).
- Exports are made on demand and not stored; the plan line changed from "stored in private file
  storage" to "made on demand".

## Design

- **Route:** `POST /internal/jobs/{id}/kits/{kitId}/export` with
  `{ "format": "pdf" | "docx", "name": string, "contact"?: string }`. It returns JSON
  `{ filename, contentType, data }` where `data` is the file in base64 (the web server's engine
  client reads JSON only); the web server turns it into a real download.
- **Name and contact are the person's own words.** The kit does not hold them (the engine knows no
  name or email). The screen asks for a name (required, at most 80 characters) and a contact line
  (optional, at most 200), prefilled from the account, and they become the header. They are not
  checked and the screen says so.
- **Checked again at export.** The version is rechecked with `kit_edit.recheck` against the facts of
  its own profile that are confirmed or edited *now* (the same recheck an edit runs, nothing saved).
  If any statement is still flagged the engine answers `409 needs_fixing` and says how many. So the
  person can unblock an export by removing or editing a statement, or by confirming or editing the
  fact in Profile, with no extra step. Older versions can be exported too; they are rechecked the
  same way.
- **Layout (ATS-friendly):** one column, text only, no tables, images or text boxes. CV: name and
  contact, then Summary, Experience, Projects, Education, Skills; each entry a bold heading line
  then bullet lines. Letter: header, "Dear hiring team,", the paragraphs, "Kind regards,", the name.
  Proposal: header, the paragraphs, the name. Answers: header, then each question in bold and its
  answer. Only these words are added by code; every other word is the version's.
- **PDF** (reportlab, A4, the bundled Vera font, so Latin letters with accents are drawn);
  characters the font cannot draw are replaced by `?` rather than a blank box. **DOCX** (python-docx, real Heading and List Bullet styles, a plain font).
- **Safety:** user text is escaped before it reaches reportlab's markup; files are built in a worker
  thread; the filename is made safe (`clean_filename`); the web response is `no-store` with an
  `attachment` disposition; nothing from the document is logged.

## In scope

- Engine: `kit_export.py` (document model, PDF and DOCX renderers), `kitting.export_kit`, the route,
  tests (the files are read back with pypdf and python-docx).
- Web: `exportKit`, `handleJobKitExport`, a route `/api/jobs/$id/kits/$kitId/export`, helpers in
  `kit-view.ts`, the export controls in `kit-step.tsx` (replacing "not built yet"), tests.
- Verify; a browser check that downloads a real file.

## Out of scope

Stored copies, templates or themes, photos, languages other than what the font draws, editing the
name or contact beyond the two fields, e-mailing a file, one-click "prepare application" (36).

## Rules

- Never export a version the engine has not rechecked just now. Another user's job, kit or facts are
  never read. A track of another type than the job is `not_found`.
- The name and contact are cleaned, length-capped and never logged.

## Build steps

- [x] 1. Engine `kit_export.py` and its tests.
- [x] 2. Engine `export_kit`, the route and tests.
- [x] 3. Web client, handler, route, helpers and tests.
- [x] 4. Export controls in `kit-step.tsx`; lint, typecheck, build.
- [x] 5. Verify, browser check, independent review, archive, merge.

## Notes for the AI

Reuse `kit_edit.recheck`, `eval_evidence.load_facts`, `storage.store.clean_filename` and the lock
pattern in `kitting.py` only if something is written (nothing is). Mirror the existing handler and
route test patterns. Keep the screen's wording plain and never imply the wording is verified.

## Step notes

- `kit_export.py`: `build_doc` (reading-order lines from a version; the only added words are the
  letter greeting and closing and the section headings), `render_pdf` (reportlab, A4, Vera font,
  characters the font lacks become `?`, user text escaped for reportlab markup, bullets are real
  `\u2022` characters inside the text so they extract cleanly) and `render_docx` (python-docx, Title,
  Heading 1 and 2 and List Bullet styles in plain black Arial).
- `kitting.export_kit`: rechecks the version with `kit_edit.recheck` against the facts of its own
  profile that are confirmed or edited now; any flag is `409 needs_fixing` (a count, never text);
  builds in a worker thread; returns `{filename, contentType, data}` (base64). Nothing is stored or
  written. An older version can be exported.
- Web: `handleJobKitExport` reuses `forward` (auth, id checks, body cap), passes a refusal through
  unchanged, validates the file (type allowlist, base64, 5 MB) and answers `attachment`, `no-store`,
  `nosniff` with a header-safe name; `exportKit` and `fileNameFrom` in `jobs-api.ts`; the screen's
  Download section (name required, contact optional, both prefilled from the account).
- Dependencies added: `reportlab` 5.1.0 and `python-docx` 1.2.0 (with `lxml`, `pillow`,
  `charset-normalizer`). mypy ignores reportlab's missing type information.
- Verify: engine 908 passed, 11 skipped; ruff, format and mypy pass. Web lint, typecheck and build
  pass; web tests 256 passed, 1 skipped.
- Not done: the Download section was not yet seen in a browser (needs an engine restart); no file
  was opened in a PDF reader or Word. The tests read both formats back with pypdf and python-docx.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":6135,"specSha256":"9bf1457acf715f82fdc315592a720c77f4f0ba8fa00e985c5178a9f669454418","branch":"refs/heads/feature/11c-pdf-and-docx-export","head":"d0aad69cfc7ec20a2186279237a10cf315d1d82f","baseRef":"refs/heads/main","baseCommit":"2c24f38f3af6d1f2faee0363bf88db6daf83b04d","sourceTree":"5903347ca66a26437b6f09674e14e38d607673cb","landing":"local-merge","absentOptional":[]} -->

## Independent review

**Status:** passed
**Target commit:** d0aad69cfc7ec20a2186279237a10cf315d1d82f
**Base commit:** 2c24f38f3af6d1f2faee0363bf88db6daf83b04d
**Base ref:** main
**Spec hash:** 9bf1457acf715f82fdc315592a720c77f4f0ba8fa00e985c5178a9f669454418
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-11T20:11:00Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-11T20:40:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Handoff

Review the active spec and the complete `main..target` delta in a fresh
session or isolated subagent without the builder conversation. Run all Audit lenses from scratch.
Do not edit product code, accept findings, or reuse the existing findings as the review scope.

## Commands

- `uv run --env-file ../.env pytest -q tests/test_kit_export.py tests/test_kitting.py tests/test_kit_routes.py tests/test_kit_edit.py tests/test_db.py` (engine): pass, 125 passed
- `npm test` (web): pass, 256 passed, 1 skipped
- `npm run lint` and `npx tsc --noEmit` (web): pass, no output
- `uv run mypy src` and `uv run ruff check src tests` (engine): pass
- Temporary probe tests for markup, control characters, long words, 3000-bullet documents, threads, odd stored shapes and stale facts: run, then removed

## Evidence

- Markup in title, contact, heading, bullet, bold and paragraph text (`<font>`, `<img src=/etc/passwd>`, `<a href>`, `<br/>`, `<seq/>`, `<para>`, `&#x41;`, `<unichar>`, `%(page)d`) comes out of pypdf as literal text; nothing reaches reportlab as markup, no file or network read, no build failure. The DOCX builds for the same input.
- Control characters, lone surrogates, U+FFFE, U+2028 and CR are removed or shown as `?` in the PDF; the DOCX builds. A 100,000-character word and a 231-page, 174 KB PDF build without error (0.55 s PDF, 1.3 s DOCX). Twelve threads building at once with the font flag reset produced no error; the TTFont state does not grow.
- Ownership: `export_kit` filters the job, the version and the track by `user_id`; track kind must match the job kind; recheck uses `load_facts` for the version's own profile; the 409 message holds only a count. Tests cover foreign, hidden and made-up ids, and that nothing is logged or saved.
- Web: engine errors pass through `forward` before the type, size and base64 checks; headers are built from a filtered name with an ASCII fallback and an encoded UTF-8 name; `nosniff` and `no-store` are set; the object URL is revoked after use; buttons are disabled while pending.
- Dependencies: reportlab, python-docx, lxml, pillow and charset-normalizer are in `uv.lock` with hashes; the mypy override covers only reportlab and is correct.

## Findings

- F-197 (P2), F-198 (P2), F-199 (P3), F-200 (P3), F-201 (P3). No P0 or P1.

## Remaining risk

- The verdict is passed because no P0 or P1 is open. Two P2 findings stay open and should be fixed before release: F-197 (stale headings and skill names in the file) and F-198 (silent `?` in the PDF).
- Not verified: opening the DOCX in Word, the PDF in a real ATS, and the screen in a browser (no DOM test). An export has no per-user rate limit or concurrency cap; each call uses a worker thread, so many parallel calls could use CPU, though a normal document builds in milliseconds. Corrupt stored content (for example `summary: null`) would raise an error in `build_doc` and give a plain 500 with no text; not reachable through the engine's own writers.
