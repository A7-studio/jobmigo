# Feature: CV storage, upload and text extraction

**From build-plan:** feature 3a
**Build attempt:** 1
**Branch:** feature/cv-storage-upload-and-text-extraction
**Status:** verified

## Goal

A signed-in user can upload a PDF or DOCX CV. The engine keeps the file in private
object storage under an unguessable key, extracts its text inside a resource-limited
child process, and records a `cv_file` row holding the display name, type, size and
extracted text. Only the owner can list, download (through a short-lived signed link)
or delete it. Local development uses a RustFS container as the S3-compatible store, so
the whole path can be tried on the founder's machine before any hosting is bought.
No AI parsing and no screens ship here; they are feature 3b.

This replaces the parked TypeScript build (`parked/ts-cv-storage-3a`, never merged):
the engine owns file parsing (the design decision of 2026-11-08), and that branch's
review findings F-50 to F-56 are this feature's test list (see Notes).

## In scope

- **Object store** in `engine/src/engine/storage/`: an `ObjectStore` protocol (`put`,
  `get`, `delete`, `signed_url`), an S3-compatible adapter (`boto3`, path-style
  addressing, Signature V4, run with `asyncio.to_thread`) and an in-memory store for
  tests. Settings from `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_KEY`,
  `STORAGE_SECRET`, optional `STORAGE_REGION` (default `us-east-1`) and optional
  `STORAGE_PUBLIC_ENDPOINT` (the host signed download links are built for, so the full
  compose stack gives the browser a reachable address; defaults to `STORAGE_ENDPOINT`).
  Read at call time, never at startup, so the engine still boots without storage.
  Unset configuration fails with `storage_not_configured`; nothing is guessed.
- **Local RustFS** as the `storage` service in `docker-compose.yml` (image pinned by
  digest, API on `127.0.0.1:9100`, console on `127.0.0.1:9101`), storage variables
  passed to the `engine` service, working local values in `.env.example`, and the
  commands in `AGENTS.md`. A missing bucket is created on first write only when
  `ENVIRONMENT=local`.
- **`engine.cv_file` table** (Alembic `0003`) and its SQLAlchemy model.
- **Text extraction in a child process.** The engine detects the type from the first
  bytes (never the filename or declared type), then runs `python -I -m
  engine.cv.worker` with the bytes on stdin. The worker applies `resource` limits to
  itself before reading anything, extracts text and prints one bounded JSON result.
  The parent enforces a wall-clock limit, kills the child on overrun, caps what it will
  read from stdout, gives the child an empty environment (no project secrets) and maps
  every non-success to `cv_unreadable`. Extraction is the only place a file is parsed.
  - PDF: `pypdf`, refused when encrypted or over the page limit.
  - DOCX: stdlib `zipfile` plus `defusedxml`; only `word/document.xml` is read, and its
    inflated bytes are counted as they are produced (declared sizes are never trusted).
  - Output: whitespace normalised; a file with no readable text (a scanned PDF) or text
    over the character limit is refused.
  - At most 2 extractions run at once per engine process; others wait.
- **CV service and internal routes** (all behind `require_user`, every query scoped by the
  verified user id): `POST /internal/cv`, `GET /internal/cv`,
  `GET /internal/cv/{id}/download`, `DELETE /internal/cv/{id}`.
- **Web routes** (TanStack Start server routes, session required, request-id wrapped):
  `POST /api/cv`, `GET /api/cv`, `GET /api/cv/$id/download` (302 to the signed URL),
  `DELETE /api/cv/$id`. The upload body is the raw file, passed on to the engine as a
  stream through a byte counter that stops at the limit, so an oversized upload never
  buffers in the web server. `callEngine` gains a streaming-body option.
- **Limits** (named constants in `engine/src/engine/cv/limits.py`, one place each):
  file 5 MiB, extracted text 200,000 characters, PDF 50 pages, inflated
  `word/document.xml` 10 MiB, DOCX entries 1,000, worker memory 512 MiB (`RLIMIT_AS`),
  worker CPU 10 s (`RLIMIT_CPU`), wall clock 15 s, worker stdout 4 MiB, list 100 rows.
  All are reversible defaults.
- **Privacy:** storage keys are `cv/<userId>/<uuid4>`, never built from the filename.
  The filename, bytes, extracted text, keys and signed URLs are never logged, never put
  in errors, and the list never includes extracted text. A signed link carries no user
  data, expires in 300 seconds, and is never stored or logged.
- **Stable errors** (`{ code, message }`): `cv_too_large` 413, `cv_unsupported_type` 415,
  `cv_unreadable` 422, `storage_not_configured` 503, `storage_unavailable` 502,
  `not_found` 404 (missing, malformed or someone else's id, same body).

## Out of scope

- AI parsing, profile drafts, `failure_reason` and every screen (3b, 4). Upload is
  exercised through tests, `curl` and the HTTP routes only.
- Virus scanning, OCR, `.doc`/`.rtf`/image uploads, per-user quotas and upload rate
  limits (no hostile-user assumption in the usage model; revisit with billing).
- A job queue or worker: extraction runs inside the upload request.
- Network or syscall sandboxing of the child (no seccomp, no namespaces); the child is
  bounded in memory, CPU, time, output and environment only.
- Removing stored objects when an account is deleted (the account-deletion feature must
  delete each file); `readyz` does not check storage yet; production R2/B2 setup and live test.
- Surfacing `storage_unavailable` or `storage_not_configured` to the browser as such: the
  web client already maps engine 5xx to `engine_unavailable`, and that is kept.

## Build loop

Per `blueprint/config.json`: `workflow.stepReview: feature`, `workflow.checkpointCommits:
disabled`. Build the steps in order on the branch above, run the narrowest check while
iterating, run Verify once after the last step, then the fresh independent review
(`qualityGates.regular.independentReview: when-sensitive` selects it for personal data,
file parsing and a new service). Continuous Mode may be driving this run.

## Build steps

- [x] 1. **Local object store and configuration.** Add the `storage` service (RustFS,
  digest pinned, host ports 9100 and 9101 bound to 127.0.0.1) to `docker-compose.yml`,
  pass the `STORAGE_*` names to the `engine` service (with `STORAGE_PUBLIC_ENDPOINT`
  defaulting to `http://localhost:9100`), add working local values to `.env.example`
  (including the live-test flag `STORAGE_LIVE_TEST` commented out), and the start command
  to `AGENTS.md`. Port the service block from `parked/ts-cv-storage-3a`
  (`git show parked/ts-cv-storage-3a:docker-compose.yml`) but do not copy its removal of
  the `engine` service. Done when `docker compose config` is valid, `docker compose up -d
  db storage` leaves the store answering on `http://localhost:9100`, and an unsigned
  request is refused with 403.
- [x] 2. **ObjectStore, S3 adapter and in-memory store.** Add `boto3` (Apache-2.0; stop
  and ask if its licence or size is unsuitable); `engine/src/engine/storage/{__init__,
  config,s3,memory}.py` and the two storage `ApiError` codes. The adapter signs with
  Signature V4, path-style, connect 5 s and read 30 s timeouts, treats a missing object
  on `get` as `None` and on `delete` as success, maps other failures to
  `storage_unavailable`, builds signed URLs locally against `STORAGE_PUBLIC_ENDPOINT`
  with `ResponseContentDisposition` (ASCII `filename` plus RFC 6266 `filename*`, control
  characters and quotes removed), and never puts keys, URLs or response bodies in errors
  or logs. Done when unit tests cover configuration errors, the in-memory store and
  filename sanitising, and `STORAGE_LIVE_TEST=1` tests against RustFS (a `jobmigo-test`
  bucket) prove put, get, overwrite, delete, a missing object, a signed URL that
  downloads without credentials, and refusal after each of these edits to a signed URL:
  path, signature (flipped deterministically), expiry and download name, with the other
  object uploaded first so a missing signature check would return 200 (F-51), plus a
  wrong secret key being refused.
- [x] 3. **Schema and migration.** `CvFile` in `engine/src/engine/models.py` and Alembic
  `0003`. Update `tests/test_db.py` for the new table and revision. Run `uv run
  --env-file ../.env alembic upgrade head` against the dev database. Done when the
  migration applies to a fresh database, a check constraint rejects an unknown `mime` or
  `parse_status` and a negative size, `storage_key` is unique, and `uv run ... pytest
  tests/test_db.py tests/test_ai_tables.py` passes.
- [x] 4. **Extraction in process (no isolation yet).** Add `pypdf` (BSD-3) and
  `defusedxml` (PSF); check both licences and that they are pinned in `uv.lock`, stop and
  ask if either is not permissive. `engine/src/engine/cv/{limits,extract}.py` with
  `extract_text(data, kind)` returning text or raising a typed reason, plus small fixture
  builders in `engine/tests/cv_fixtures.py` that generate PDFs and DOCX in memory. The
  DOCX path counts inflated bytes in chunks and stops at the limit (F-50 holes 1 and 2:
  a central directory with a hidden entry and with an understated size are both bounded
  because only counted bytes matter), rejects a DOCTYPE, and requires `word/document.xml`.
  Done when tests prove: a PDF and a DOCX return their text; a ZIP with no
  `word/document.xml` is `unsupported`; an encrypted PDF, a PDF with no text, a corrupt
  file, a 60-page PDF and over-long text are refused; whitespace is normalised; a
  generated bomb (small file, 400 MB of `document.xml`), a DOCX with a hidden extra
  central-directory entry and one whose directory understates the size are each refused
  after reading no more than the limit plus one chunk (asserted with a counting wrapper,
  not process memory); extracted text never appears in an error message.
- [x] 5. **Isolated extraction.** `engine/src/engine/cv/{worker,runner}.py`: the worker
  applies `resource.setrlimit` (`RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_NOFILE`, no core
  files) before reading stdin; the runner spawns it with an empty environment and
  `stdin`/`stdout` pipes and `stderr` to `/dev/null`, enforces the wall clock, kills the
  child on overrun, caps stdout, bounds concurrency with a semaphore of 2, and maps
  timeout, signal, non-zero exit, oversized or malformed output to `cv_unreadable`. The
  runner takes the command and timeout as parameters (test seam). Check that `python -I -m
  engine.cv.worker` runs from the project environment under pytest and in the engine
  image. Done when tests prove: results from the isolated path equal the in-process
  results for the step 4 fixtures; a child that sleeps past the wall clock is killed and
  reported `cv_unreadable` within a second of the limit; a child that prints more than the
  stdout cap is stopped; the child does not see `ENGINE_TOKEN` or `DATABASE_URL`; and, on
  Linux only (`skipif`), a PDF whose Flate content stream inflates to 300 MB and a worker
  that allocates past the cap are killed by the limits and refused (F-50 hole 3, F-54),
  with the engine process memory unchanged. Run those Linux tests once in Docker (command
  recorded in `AGENTS.md`) because `RLIMIT_AS` is not enforced on macOS.
- [x] 6. **CV service and internal routes.** `engine/src/engine/cv/{service,routes}.py`,
  registered in `main.py` under the existing `/internal` router. Raw-body upload: reject
  `Content-Length` over the limit before reading, then count the stream and stop at the
  limit (`cv_too_large`); filename from `X-Filename` (percent-encoded UTF-8, control
  characters removed, path separators dropped, at most 200 characters, default `cv`);
  order is validate, extract, put, insert, and the stored object is removed if the insert
  fails; delete removes the object then the row, keeps the row and returns
  `storage_unavailable` on a storage failure, and always filters by `user_id` in the
  statement itself (F-56). Download returns `{ url, expiresInSeconds: 300 }`. The store
  and the extractor come from `app.state` so tests inject the memory store. Done when
  database-backed tests (`jobmigo_engine_test`, memory store) prove: a good upload creates
  one object and one row with the detected mime and size and returns no text; an oversized
  (by header and by stream), unsupported or unreadable file stores nothing; a missing,
  malformed or other user's id is 404 with the same body for download and delete; list
  returns only the caller's rows, newest first, with no text; a failed insert removes the
  object; a storage failure on delete keeps the row; missing token is 401 on every route;
  and across success, failure and cleanup-failure paths nothing logged contains the
  filename, key, text or signed URL (F-53, F-56), including the S3 adapter with a failing
  `boto3` stub.
- [x] 7. **Web routes and streaming client.** Extend `callEngine`
  (`web/src/server/engine/client.ts`) with an optional streaming body and extra headers
  (`duplex: 'half'`, longer timeout for upload) without weakening its path and redirect
  rules. Add `web/src/server/cv/http.ts` (handlers: `requireUser`, UUID check on `$id`
  before any engine call, `Content-Length` pre-check, a counting `TransformStream` that
  records when it cut the stream so the response is `cv_too_large` 413 and not
  `engine_unavailable`, pass-through of the engine's stable 4xx, download answered as 302
  with `cache-control: no-store`) and the route files `web/src/routes/api/cv/{index,
  $id/index,$id/download}.ts`. Done when Vitest (injected `fetchFn`) proves: every route
  is 401 without a session and makes no engine call; an over-limit `Content-Length` is
  413 and nothing is sent to the engine; a chunked body over the limit is 413 and
  the engine call is aborted; the filename is forwarded percent-encoded and the user id
  is the session's, never client input; the engine's 413, 415, 422 and 404 reach the
  client unchanged; download returns 302 whose `Location` is the engine's URL; list and
  delete pass through; the generated route tree has the four method and path pairs
  (F-53); no log call contains the filename or URL; and the built production server
  (`npm run build`, `npm start`) accepts a streamed upload of a real 1 MB file to the
  engine with a throwaway local account (manual, recorded).
- [x] 8. **Production wiring, docs and final checks.** Add the `STORAGE_*` names to the
  `engine` service in `deploy/docker-compose.prod.yml` and to
  `deploy/.env.production.example` (names only, no values); update
  `docs/technical-design.md` (storage section, config names, the child-process limits),
  `docs/database-design.md` (`cv_file` as built), `docs/ai-workflows.md` only if it
  mentions CV parsing, and `AGENTS.md` (storage, live test and Linux limit commands). Done
  when the full Verify command passes with RustFS running, `STORAGE_LIVE_TEST=1` passes
  once, the Linux limit tests passed once in Docker, an end-to-end manual run through the
  built web server with RustFS (upload a PDF and a DOCX, list, download via the signed
  link, delete, confirm the object is gone from the bucket) is recorded, and the docs name
  every new variable, route and limit.
- [x] 9. **Repair the independent review's P3 findings (F-64 to F-67).** DOCX parsing
  detaches each finished element from its parent (memory follows nesting depth, not
  element count); a failed or cancelled insert removes the stored object (shielded delete,
  re-raise); the extraction child is signalled only while it is still running; a
  non-ASCII `Content-Length` is ignored instead of raising. Done when each fix has a test
  that fails without it (element-flood memory, cancelled upload, reaped child, `Content-Length`
  of `²`) and the engine gate and the Linux limit tests pass.

## Files / areas

- New (engine): `engine/src/engine/storage/*`, `engine/src/engine/cv/{limits,extract,
  worker,runner,service,routes}.py`, `engine/migrations/versions/0003_cv_file.py`,
  `engine/tests/{cv_fixtures,test_storage_*,test_cv_*}.py`
- New (web): `web/src/server/cv/http.ts`, `web/src/routes/api/cv/{index,$id/index,
  $id/download}.ts`, `web/tests/cv-*.test.ts`
- Changed: `engine/src/engine/{models,main,errors}.py` (errors only if a shared helper is
  needed), `engine/pyproject.toml` and `engine/uv.lock` (`boto3`, `pypdf`, `defusedxml`;
  mypy override for `boto3`/`botocore`), `engine/tests/test_db.py`,
  `web/src/server/engine/client.ts`, `docker-compose.yml`, `deploy/docker-compose.prod.yml`,
  `deploy/.env.production.example`, `.env.example`, `docs/*`, `AGENTS.md`
- Untouched: components and screens, auth, the waitlist, the AI gateway, `public` schema

## Data / contracts

- `engine.cv_file`: `id` uuid pk default `gen_random_uuid()`; `user_id` uuid not null (no
  foreign key, per the engine rule), index on `(user_id, created_at)`; `storage_key` text
  not null unique (`cv/<userId>/<uuid4>`); `filename` text not null (display only, at most
  200 characters); `mime` text not null check in (`pdf`, `docx`); `size_bytes` integer not
  null check >= 0; `extracted_text` text not null (never empty, at most 200,000
  characters); `parse_status` text not null default `extracted` check in (`extracted`,
  `parsing`, `parsed`, `failed`) (later values belong to 3b); `created_at`, `updated_at`
  timestamptz not null default `now()`.
- Upload: `POST /api/cv` and `POST /internal/cv`, body is the raw file bytes,
  `X-Filename: <encodeURIComponent(name)>`; `Content-Type` is ignored. Success 201
  `{ id, filename, mime, sizeBytes, parseStatus, createdAt }` (camelCase, ISO 8601 UTC).
- List: `GET` returns `{ items: [<same shape>] }`, newest first, at most 100.
- Download: engine `GET /internal/cv/{id}/download` returns `{ url, expiresInSeconds: 300 }`;
  web `GET /api/cv/{id}/download` answers 302 with that `Location`.
- Delete: 204 on success; a missing, malformed or foreign id is 404 `not_found`, same body.
- Child protocol: argv `[kind]` with `kind` in (`pdf`, `docx`); stdin raw bytes; stdout one
  JSON line `{"ok": true, "text": "..."}` or `{"ok": false, "reason": "<code>"}` with `code`
  in (`unsupported`, `unreadable`, `no_text`, `too_long`, `too_many_pages`, `too_large`).
  `unsupported` maps to 415, every other reason, a crash, a timeout or bad output to 422.
- Type detection: `%PDF-` at byte 0 is a PDF candidate; `PK\x03\x04` at byte 0 is a DOCX
  candidate confirmed by the worker; anything else is 415 before a process starts.
- Signed link: Signature V4, region `STORAGE_REGION`, path-style
  `{STORAGE_PUBLIC_ENDPOINT or STORAGE_ENDPOINT}/{bucket}/{key}`, 300 seconds.

## Testing

pytest with the real `jobmigo_engine_test` database and the in-memory store for service
and route tests; the S3 adapter's tests against RustFS run only with `STORAGE_LIVE_TEST=1`
(skipped otherwise, and a failure when the flag is set but the store is unreachable).
Fixtures are generated in memory by `cv_fixtures.py`; hostile files are built in the test
and stay small on disk. The memory-limit tests are Linux-only and are run once in Docker.
Web tests use Vitest with an injected `fetchFn`. No browser tests (no UI). Step 7 and step 8
include manual checks of the built server; they are recorded as observed, not claimed as
automated.

## Notes for the AI

- Follow existing patterns: `ApiError` and the `{ code, message }` shape, `require_user` on
  the `/internal` router, `Database` and the `models.py` conventions, JSON logging, tests
  under `engine/tests` using `conftest.py`; on the web side `callEngine`, `requireUser`,
  `withRequestId`, `DomainError`.
- Reuse from `parked/ts-cv-storage-3a` only through `git show <ref>:<path>` (compose
  service block and digest, `.env.example` names, route file shape). Do not merge or
  cherry-pick it, and do not delete it.
- Findings carried from the parked branch as the test list: F-50 (all three bypasses, step
  4 and 5), F-51 (signed-URL tamper cases, step 2), F-52 (digest pin and 127.0.0.1 binding,
  step 1), F-53 (route registration and no-logging, steps 6 and 7), F-54 (hostile fixtures
  and the real isolation mechanism, steps 4 and 5), F-55 (`STORAGE_PUBLIC_ENDPOINT`, step 2),
  F-56 (owner condition in the delete statement and logging of adapter failures, step 6).
- Never log filenames, bytes, extracted text, storage keys, signed URLs or response bodies
  from storage. Pass the child only an empty environment. The parser child is bounded, not
  sandboxed; say so in the docs.
- Do not add libraries beyond `boto3`, `pypdf` and `defusedxml`. If one looks unsuitable
  (licence, size, maintenance) stop and ask instead of swapping.
- Read storage settings from the environment at call time; the engine must still boot with
  storage unset.
- Every limit is one named constant in `limits.py`. `RLIMIT_AS` is not enforced on macOS,
  so never claim memory-limit behaviour from a macOS run.
- Ruff `S` rules apply to the subprocess code; add a targeted `noqa` with a reason, not a
  file-wide ignore.

## Open questions

None that block the build. Decisions for later features: the production object storage
provider (R2 or B2) and when `readyz` checks it, where account deletion removes stored
files, and whether 3b's upload screen sends the raw body (the contract here) or wraps it.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":21339,"specSha256":"e9592d8f6796963f7ae1ff0e2a45905c855ad17d0fc4ce8e5844048f65b40038","branch":"refs/heads/feature/cv-storage-upload-and-text-extraction","head":"5ebeebdcc0b4fd4c812c53a981151396c3f26638","baseRef":"refs/heads/main","baseCommit":"8ae1061680d6e25df2cac2d4c8de9e85359874ae","sourceTree":"51e73f870d9f7d53254e6592b9f8e2d43edced1a","landing":"local-merge","absentOptional":[]} -->

## Findings

### 3a/F-64 [P3] closed - DOCX parsing keeps every non-paragraph element in memory, so a small file costs about 20x its XML size

**File:** engine/src/engine/cv/extract.py:125
**Found:** 2026-11-09 by /audit (scope: current; lens: performance)
**Why it matters:** `_docx_text` clears only `w:p` elements, so a 10 MB `word/document.xml` made of empty runs (a 15 KB upload) was measured at about 207 MB peak memory and 1.6 s in-process, and then returned `no_text` (422). The 10 MiB inflated cap bounds the input, and the child's `RLIMIT_AS` (Linux only) bounds the damage, but at the 512 MiB cap a legitimate large DOCX or an element-flood file can be killed and reported as `cv_unreadable`. The in-process bound the spec promised ("each holds even without the child") does not cover memory.
**Suggested fix:** In the iterparse loop, call `element.clear()` on every `end` event after reading its text (not just `w:p`), and add a Linux test with an element-flood DOCX at the limit.
**Resolution:** Fixed: `_docx_text` removes each finished element from its parent (start/end events), so memory follows nesting depth; test `test_an_element_flood_costs_far_less_memory_than_its_xml_size` (peak under 2x the XML, was about 20x).
Re-examined 2026-11-09 by independent review (5ebeebd): confirmed. The loop pairs start/end events, pops the open stack and removes each finished element from its parent (O(1), it is the only child); the flood test passes. The repair introduced no defect. Nesting depth is still unbounded, which is a different input shape (see F-68).

### 3a/F-65 [P3] closed - A cancelled upload between `store.put` and the insert leaves an orphaned object

**File:** engine/src/engine/cv/service.py:125
**Found:** 2026-11-09 by /audit (scope: current; lens: quality)
**Why it matters:** The cleanup is `except Exception`, which does not catch `asyncio.CancelledError` (a `BaseException`). If the request task is cancelled while the row is being inserted, the stored object stays with no row and nothing references it. A process crash at the same point has the same result. Impact is stray storage cost, not exposure (keys are unguessable and private); a sweeper is out of scope for this feature.
**Suggested fix:** Catch `BaseException` (or use `try/finally` with a success flag) so the delete runs on cancellation too, shielded with `asyncio.shield`, and re-raise.
**Resolution:** Fixed: the cleanup catches `BaseException` and runs a shielded delete before re-raising; test `test_a_cancelled_upload_leaves_no_stored_object`.
Re-examined 2026-11-09 by independent review (5ebeebd): confirmed. `service.py` catches `BaseException`, runs `asyncio.shield(store.delete(key))`, tolerates `StorageUnavailableError` and re-raises; the test passes. The repair introduced no defect; two residual windows are filed as F-69.

### 3a/F-66 [P3] closed - The extraction child's process group is signalled after it has already been reaped

**File:** engine/src/engine/cv/runner.py:69
**Found:** 2026-11-09 by /audit (scope: current; lens: security)
**Why it matters:** `_kill` runs `os.killpg(process.pid, SIGKILL)` in `finally` on every path, including after `process.wait()` returned and asyncio reaped the child. Once reaped, the pid (and the group id, if no other member remains) can be reused, so the signal could reach an unrelated process group. The window is tiny and needs pid reuse, so this is a hygiene defect, not an observed failure.
**Suggested fix:** Skip the kill when `process.returncode is not None` and no group member can remain (or only kill on the timeout and error paths).
**Resolution:** Fixed: `_kill` returns when the child was already reaped; test `test_an_already_reaped_child_is_not_signalled`.
Re-examined 2026-11-09 by independent review (5ebeebd): confirmed. `_kill` returns when `returncode` is set and checks it with no await before `killpg`; the timeout, output-cap and cancellation paths still kill the group and then wait. The orphaned `_feed` task swallows broken-pipe errors. No new defect.

### 3a/F-67 [P3] closed - A non-ASCII digit in `Content-Length` raises a 500 in the engine upload route

**File:** engine/src/engine/cv/routes.py:31
**Found:** 2026-11-09 by /audit (scope: current; lens: quality)
**Why it matters:** `declared.isdigit()` is true for characters such as `²` (Latin-1 header bytes), and `int()` then raises `ValueError`, which becomes `internal_error` 500 instead of being ignored. Only the trusted web server calls this route and it sends its own length, so it is not reachable by a browser today.
**Suggested fix:** Parse with `try: int(declared)` and check `declared.isascii()` (or ignore a bad value), keeping the stream count as the real limit.
**Resolution:** Fixed: `_declared_length` accepts only ASCII digits and otherwise ignores the header; test `test_a_non_ascii_content_length_is_ignored_not_a_500`.
Re-examined 2026-11-09 by independent review (5ebeebd): confirmed. `_declared_length` requires `isascii()` and `isdigit()`, and the stream count in `read_body` stays the real limit; the test passes. No new defect.

## Independent review

Original passing receipt for checkpoint `5ebeebdcc0b4fd4c812c53a981151396c3f26638`, copied unchanged:

````markdown
**Status:** passed
**Target commit:** 5ebeebdcc0b4fd4c812c53a981151396c3f26638
**Base commit:** 8ae1061680d6e25df2cac2d4c8de9e85359874ae
**Base ref:** main
**Spec hash:** e9592d8f6796963f7ae1ff0e2a45905c855ad17d0fc4ce8e5844048f65b40038
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-09T11:43:05Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-09T11:58:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Handoff

Review the active spec and the complete `<base>..<target>` delta in a fresh
session or isolated subagent without the builder conversation. Run all Audit lenses from scratch.
Run Check when required above. Do not edit product code, accept findings, or
reuse the existing findings as the review scope.

## Commands

- `git rev-parse HEAD`, merge-base with main, spec sha256, `git status`: pass (HEAD equals target, base and spec hash match, only review.md and findings.md differ)
- `git diff 8ae1061..5ebeebd` (45 files) read across the engine CV, storage and web handler code: pass
- `npm run lint` (web): pass
- `npm run typecheck` (web): pass
- `npm test` (web): pass (103 passed, 1 skipped)
- `uv run ruff check .` (engine): pass
- `uv run ruff format --check .` (engine): pass
- `uv run mypy` (engine): pass
- `uv run --env-file ../.env pytest -q` (engine): pass (165 passed, 8 skipped)
- In-process nested-DOCX probe and lone-surrogate round trip (scratch script, no repo writes): ran, produced F-68 and F-70

## Evidence

- Owner scoping: list, download and delete in `engine/src/engine/cv/service.py` all filter on `CvFile.user_id`; upload sets `user_id` from the authenticated user; keys are `cv/<user>/<uuid4>`.
- Upload limits: web `limitStream` and declared-length check, engine `read_body` counts the stream against 5 MiB and refuses early; the filename header is ASCII-only, percent-decoded, stripped of control characters and separators.
- Extraction isolation: child runs `python -I` with an empty environment, no stderr, its own session, RLIMIT_CPU/CORE/NOFILE (RLIMIT_AS on Linux), wall timeout, 4 MiB output cap and a two-slot semaphore; DOCX inflated bytes counted as produced, entry count capped, DTD and entities forbidden through defusedxml; PDF page and text caps.
- Signed URLs and redirects: engine builds a 300 s presigned GET with a sanitised `Content-Disposition` (quotes, percent, semicolon replaced; controls removed); web download returns a no-store 302 only for an http(s) URL from the engine; the engine client uses `redirect: 'error'`.
- Logging: only error class names and operation names are logged; no filename, key, URL or extracted text.
- Ledger: F-64, F-65, F-66 and F-67 re-examined against the code and tests and closed, each with evidence in its Resolution. F-42 to F-49 left untouched.

## Findings

- New, all P3 and open: F-68 (unbounded DOCX nesting depth), F-69 (cleanup misses a cancelled put and can delete the object of a committed row), F-70 (lone surrogate in PDF text gives a 500). No P0, P1 or P2.
- Closed: F-64, F-65, F-66, F-67.

## Remaining risk

- RLIMIT_AS memory limits are Linux only and were not exercised here (the Docker-based limit tests are skipped on macOS); the PDF bomb path was reviewed in code, not run.
- F-70 was verified up to the encode failure, not with a crafted PDF end to end.
- Live storage tests (`STORAGE_LIVE_TEST`) and engine live client tests were skipped, so the S3 adapter against a real store and the presigned URL behaviour were not run here.
- Cross-site request forgery on the web upload and delete routes relies on session cookie SameSite defaults; not tested here.
````

## Try guide

Skipped by the user's decision at completion: `/check guide` is user-run and was not available to the completing session. Run `/check guide latest` for a walkthrough.
