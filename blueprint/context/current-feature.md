# Feature: AI parse into a profile draft (engine)

**From build-plan:** feature 3b
**Build attempt:** 1
**Branch:** feature/ai-parse-into-a-profile-draft-engine
**Status:** verified

## Goal

Turn a stored CV's extracted text into a structured **profile draft** of unconfirmed facts,
in the engine, in the background, through the AI gateway's cheap tier. A signed-in user (the
web server vouches for them) can start a parse, poll its status, retry a failure and read
the draft. Nothing is confirmed here: every row is `status = extracted`, and only feature 4
confirms or edits facts. The `/onboarding` upload and status screen is feature 3c; 3b ends
at the engine routes and the matching web API routes.

## In scope

1. **Draft tables** in the `engine` schema (Alembic `0004`): `profile`, `experience`,
   `skill`, `achievement`, `project`, `education`, and `cv_file.parse_error`. Every row has
   `user_id`; `profile.source_cv_id` references `cv_file(id) ON DELETE CASCADE` (same schema),
   and children cascade from `profile`, so deleting a CV also deletes the draft derived from it.
2. **The parse task** (`cv/parse.py`): an `AiTask` on the `cheap` tier, workflow `parse`,
   prompt version `cv-parse-v1`, `cache=False` (see Notes), with Pydantic input and output
   models, output bounds and text cleaning. The CV text is untrusted data placed inside a
   delimited block, with an instruction to ignore any instructions inside it; the output is
   schema-validated and stored only as unconfirmed draft rows.
3. **Background run** inside the engine: an atomic claim (`extracted|failed` to `parsing`),
   an `asyncio` task that calls the gateway and writes the whole draft and the `parsed`
   status in one transaction, a stable failure code on every failure path, and a startup
   sweep that turns rows left in `parsing` by a restart into `failed` / `interrupted`.
4. **Engine routes** under `/internal/cv` (router-level auth already applies):
   `GET /{id}` (one CV's status), `POST /{id}/parse` (start or retry), `GET /{id}/profile`
   (the draft). `CvOut` gains `parseError`.
5. **Web API routes** that forward them for the signed-in user: `GET /api/cv/$id`,
   `POST /api/cv/$id/parse`, `GET /api/cv/$id/profile`, with the same UUID check and error
   mapping as the existing CV handlers.
6. **Privacy notice**: a short "Your CV" section on `/privacy` that names DeepSeek as the
   provider that receives CV text, only when the user asks for a parse. This is in 3b
   because CV text first leaves the system here.
7. **Docs and commands**: `docs/technical-design.md`, `docs/database-design.md`,
   `docs/ai-workflows.md` (if it lists the parse task), `AGENTS.md` (live parse check).

## Out of scope

- The upload and status screen, polling UI, progress and failure copy (3c).
- Editing, confirming or deleting individual draft facts, choosing the "current" profile,
  variants and tracks (4). Evidence references and `used_in_role` on skills (added by the
  feature that first uses them).
- A job queue, worker or `background_job` table (the engine's in-process task is enough at
  tens of users; revisit with the worker), per-user quotas and credits (16), account-deletion
  hooks, the `strong` tier, BYOK.
- Starting a parse automatically on upload: the web layer asks for it explicitly.
- OCR for scanned PDFs, language detection, and any non-English handling beyond what the
  model returns.

## Build loop

Follow `blueprint/config.json`: `workflow.stepReview: feature` (build all steps, one final
review packet), `checkpointCommits: disabled`. Run the narrow check for each step, the full
Verify once at the end. Independent review is required (`when-sensitive`: personal data and
a new external side effect), so a verified spec leads to an approved checkpoint commit and
`/audit independent current`.

## Build steps

- [x] 1. **Draft schema.** Add `CvFile.parse_error` (text, null unless `parse_status =
  'failed'`, check constraint) and the six draft tables to `engine/src/engine/models.py`;
  Alembic `engine/migrations/versions/0004_profile_draft.py` (upgrade and downgrade);
  update `tests/test_db.py` for `0004`. Limits for row counts and field sizes live in
  `cv/limits.py`. Done when `alembic upgrade head` from scratch and a downgrade to `0003`
  both succeed in the test database, inserting a profile with children works, deleting the
  `cv_file` row removes the profile and every child, and the constraint rejects a
  `parse_error` on a non-failed row (`uv run pytest tests/test_db.py tests/test_cv_table.py`
  pass; add `tests/test_cv_profile_table.py`).
- [x] 2. **Parse task and output model.** `engine/src/engine/cv/parse.py`: input model
  (`text`), `ParsedProfile` output model with `extra="forbid"`, bounded lists and string
  lengths, partial-date validation (`YYYY` or `YYYY-MM` or null), control-character stripping
  and whitespace normalisation, the `AiTask` definition, and `parse_cv_text(text, user_id,
  database, env, provider)` that enforces the text-length cap before any model call and
  rejects an empty draft. Done when focused tests with a fake provider prove: a valid reply
  parses; unknown keys, over-long strings, too many rows and bad dates are rejected; the gateway's one
  retry recovers from an invalid first reply; text over the cap fails with `text_too_long` before any
  model call and an all-empty draft fails with `no_profile_found`; the user message wraps the
  text in the delimiter; the ledger gets one `parse` event and holds no text
  (`uv run pytest tests/test_cv_parse.py`).
- [x] 3. **Service and background run.** `engine/src/engine/cv/service.py` additions (or a
  small `cv/parse_service.py` if `service.py` gets too long): `start_parse` (owner-scoped
  atomic claim with `UPDATE ... WHERE id AND user_id AND parse_status IN
  ('extracted','failed') RETURNING`), the task runner kept in a set on `app.state` so it is
  not garbage collected, the single-transaction draft write that only commits when the row is
  still `parsing` (a CV deleted mid-parse writes nothing), failure mapping to the stable
  codes below, the startup sweep wired in the app lifespan, and cancellation on shutdown.
  Done when DB-backed tests with a fake provider prove: success writes the draft and sets
  `parsed`; each failure code is stored and clears on a successful retry; a second start
  while `parsing` is a no-op; a `parsed` CV is not re-run; another user's CV is
  indistinguishable from a missing one; deleting the CV during the run leaves no profile
  rows; the sweep fails only stale `parsing` rows; nothing sensitive reaches the logs
  (`uv run pytest tests/test_cv_parse_service.py`).
- [x] 4. **Engine routes.** `GET /internal/cv/{id}`, `POST /internal/cv/{id}/parse` (202 with
  the current status; 200 when already `parsed`; a preflight returns `503 ai_not_configured`
  before the claim when the cheap tier or its key is missing, skipped when a test provider is
  injected), `GET /internal/cv/{id}/profile` (404 until `parsed`); `CvOut` and its list gain
  `parseError`. Test seams: `app.state.ai_provider` and `app.state.ai_env`. Done when route
  tests through the ASGI app prove the statuses and bodies in Data / contracts, the 404 body
  is identical for missing, malformed and foreign ids, and every route still requires the
  bearer token (`uv run pytest tests/test_cv_parse_routes.py tests/test_cv_routes.py`).
- [x] 5. **Web routes.** Add `handleStatus`, `handleParse`, `handleProfile` to
  `web/src/server/cv/http.ts` and routes `web/src/routes/api/cv/$id/index.ts` (add GET),
  `.../$id/parse.ts`, `.../$id/profile.ts`; regenerate `routeTree.gen.ts`. Check first that
  `callEngine` passes 202 and 200 JSON bodies through. Done when handler and route tests prove
  401 without a session, the UUID check before any engine call, engine errors mapped as for
  the other CV routes, and engine 5xx as `engine_unavailable` (`npm test`).
- [x] 6. **Privacy notice, docs and final checks.** Add the "Your CV" section to
  `web/src/routes/privacy.tsx`; update the docs listed above and the `AGENTS.md` command for
  the live parse check (`tests/test_cv_parse_live.py`, skipped unless `AI_LIVE_TEST=1`).
  Done when the full Verify command passes; the live parse test passes once against DeepSeek
  with a synthetic CV when `AI_CHEAP_MODEL` and `DEEPSEEK_API_KEY` are set (otherwise it is
  recorded as not run, never claimed); an end-to-end run through the built web server and
  engine (upload, parse, poll, read draft, delete) is recorded when the live provider is
  available; and the privacy page text matches the data flow.

## Files / areas

- `engine/src/engine/models.py`, `engine/migrations/versions/0004_profile_draft.py`,
  `engine/src/engine/cv/{limits,parse,service,routes}.py`, `engine/src/engine/main.py`
  (lifespan sweep and shutdown), `engine/tests/test_db.py`, new `tests/test_cv_profile_table.py`,
  `test_cv_parse.py`, `test_cv_parse_service.py`, `test_cv_parse_routes.py`,
  `test_cv_parse_live.py`.
- `web/src/server/cv/http.ts`, `web/src/routes/api/cv/$id/{index,parse,profile}.ts`,
  `web/src/routeTree.gen.ts`, `web/src/routes/privacy.tsx`, `web/tests/cv-http.test.ts`,
  `web/tests/cv-routes.test.ts`.
- `docs/technical-design.md`, `docs/database-design.md`, `docs/ai-workflows.md`, `AGENTS.md`.

## Data / contracts

**Tables** (engine schema, all `id uuid pk default gen_random_uuid()`, `user_id uuid not
null`, `created_at timestamptz default now()`):

| Table | Columns |
|---|---|
| `profile` | `source_cv_id` uuid not null unique FK `cv_file` cascade; `headline` text null; `summary` text null |
| `experience` | `profile_id` FK cascade; `position` int; `company`; `role`; `start`, `end` text null (`YYYY` or `YYYY-MM`); `is_current` bool; `bullets` jsonb (list of text); `status` |
| `skill` | `profile_id`; `position`; `name`; `status` |
| `achievement` | `profile_id`; `position`; `text`; `experience_id` FK null on delete set null; `status` |
| `project` | `profile_id`; `position`; `name`; `description` null; `status` |
| `education` | `profile_id`; `position`; `institution`; `qualification` null; `start`, `end` null; `status` |

`status` is `extracted | confirmed | edited`, always `extracted` here (check constraint). Each
child has an index on `(profile_id, position)`. `cv_file.parse_error` is one of the codes
below or null.

**Output bounds** (reversible defaults in `limits.py`): headline 200 chars, summary 2,000,
at most 30 experiences (company and role 200 each, 20 bullets of 500), 100 skills (80),
100 achievements (500), 20 projects (name 120, description 1,000), 10 education entries
(200). Control characters are stripped and whitespace collapsed before storing.
Achievements point to an experience by its index in the reply.

**Parse input cap:** `PARSE_MAX_CHARS = 60,000` characters of extracted text. Longer text
fails with `text_too_long`; it is never silently truncated (that would drop facts).

**Status values** (`parseStatus`, existing): `extracted`, `parsing`, `parsed`, `failed`.
**Failure codes** (`parseError`, never a message or model text): `ai_not_configured`,
`ai_unavailable`, `ai_output_invalid`, `ai_input_invalid`, `text_too_long`,
`no_profile_found` (the reply had no experience, skills, education or projects),
`interrupted` (engine restarted mid-parse), `internal`.

**Engine routes** (camelCase JSON like the existing `CvOut`):

| Route | Result |
|---|---|
| `GET /internal/cv/{id}` | 200 `CvOut` (with `parseStatus`, `parseError`); 404 `not_found` |
| `POST /internal/cv/{id}/parse` | 202 `{id, parseStatus: "parsing", parseError: null}` after a claim, or the same body when already `parsing`; 200 with `parsed` when done; 503 `ai_not_configured` before any claim; 404 |
| `GET /internal/cv/{id}/profile` | 200 draft; 404 `not_found` until `parsed` |

Draft body: `{id, cvId, headline, summary, experiences:[{id, company, role, start, end,
isCurrent, bullets, status}], skills:[{id, name, status}], achievements:[{id, text,
experienceId, status}], projects:[{id, name, description, status}], education:[{id,
institution, qualification, start, end, status}]}`, ordered by `position`.

**Web routes** mirror these under `/api/cv/$id`, session required, `$id` checked as a UUID
before any engine call, engine 4xx codes passed through, engine 5xx as `engine_unavailable`.

**Trust and tenancy:** the user id comes only from the engine's authenticated header; every
statement filters on `user_id` (claim, update, draft read, sweep excepted: it is global and
touches only status and code). The CV text is untrusted input; the model has no tools, its
output is validated and stored as unconfirmed rows, and nothing from the file or the reply is
logged. Only the gateway's existing log fields (task, provider, model, cache flag, duration)
and the failure code are logged. `usage_event` rows hold no text.

## Testing

- Engine: pytest with a fake `AiProvider` and the real test database (no network). Cover every
  rule named in the steps; add a negative test per failure code and a test that the log
  capture never holds CV text, names or model output.
- Web: Vitest handler and route tests with injected `fetchFn`.
- Live: `tests/test_cv_parse_live.py` (one real DeepSeek call with a synthetic CV, skipped
  unless `AI_LIVE_TEST=1`); end-to-end run through the built server when the provider is
  configured. Neither is claimed if it was not run.
- No browser tests (no UI in 3b).

## Notes for the AI

- Reuse `run_task`, `AiTask`, `read_tier` and `create_provider`; do not add a provider
  abstraction or a queue. Follow the structure of `cv/service.py` and `cv/routes.py`.
- `cache=False` on purpose: a parse is only re-run after a failure (failures are not cached),
  and a cache would keep a second copy of derived CV data outside the owned tables.
- One draft per CV (`source_cv_id` unique); a second CV gets its own draft. Which draft is
  "the" profile is feature 4's decision. A retry only runs from `failed`, when no draft exists.
- Single engine instance: the in-process task and the startup sweep assume it. Running more
  replicas needs the worker queue first (state this in the technical design).
- Privacy copy must say only what is true: text is sent to DeepSeek only when the user starts
  a parse; do not claim deletion of provider-side copies or export, which are not built.
- Per the project rule, the design canvas matters for UI; there is no UI here, and 3c carries
  the screen. Do not add screens in this feature.
- Do not edit the build plan or overview from this feature. The overview's source hash will
  differ until the user runs `/overview` (the plan was split into 3b and 3c).

## Open questions

- Which DeepSeek model id and per-million prices go in `AI_CHEAP_MODEL` and
  `AI_CHEAP_PRICE` (and a `DEEPSEEK_API_KEY`)? This does not block the build or the tests
  (a fake provider is used); it blocks only the live parse check and the end-to-end run in
  step 6, which will be recorded as not run until the values are in `.env`.
