# Proposal: a Python AI engine beside the TanStack Start app

**Status:** draft for review. Nothing in the plans, the code or the overview has been
changed yet. Approving this proposal means the edits in section 6 are made next.

## 1. Decision and why

The project becomes a hybrid. TanStack Start stays the web app and owns accounts,
sign-in, the waitlist, billing, the CRM and the UI. A new Python FastAPI service, the
**engine**, owns everything that needs a model or a document parser: the AI gateway and
usage ledger, CV storage and text extraction, CV parsing, job evaluation and its golden
set, the application kit and later outreach drafts.

Why: the project doubles as a demonstration of AI engineering, Python is the expected
language for that work, and document parsing needs real process isolation (the review of
feature 3a showed hostile PDFs and DOCX files defeating in-process limits in Node).
Shipping can wait.

**Boundary rule:** if it calls a model or parses a file, it lives in the engine with its
data. Everything else stays in TypeScript.

## 2. Architecture

```
Browser -> TanStack Start (web) --internal HTTP--> Engine (FastAPI)
              |                                       |
              +---- Postgres (schema public) ---------+---- Postgres (schema engine)
                                                      +---- object storage (CV files)
                                                      +---- model providers
```

- **Services:** `web` (existing), `engine` (new), Postgres, object storage. No public
  port for the engine: it is reachable only on the Docker network or localhost.
- **Auth between services:** the web server calls the engine with
  `Authorization: Bearer <ENGINE_TOKEN>` and `X-User-Id`, set from the verified Better
  Auth session. The engine never sees cookies and never trusts a browser. Every engine
  query is scoped by that user id. A missing or wrong token is 401.
- **Data ownership:** one Postgres, two schemas. Drizzle owns `public`; the engine owns
  schema `engine` through Alembic. No cross-schema foreign keys. The engine tables are
  `usage_event`, `ai_cache`, `cv_file`, then profile, evaluation and kit tables as those
  features arrive. Account deletion calls an engine endpoint that removes a user's rows
  and stored files. Backups are unchanged (one database).
- **Uploads:** the browser posts to a web route, which streams the body to the engine.
  The engine stores the file (boto3 or aioboto3 with real SigV4, replacing the
  hand-written signer), and extracts text in a **subprocess with memory and CPU limits
  and a wall-clock timeout**, reading ZIP and PDF data with byte-counted limits.
- **Background work:** in-process tasks with a status column to start (same decision as
  before); a Postgres job table and worker later.
- **Tooling:** Python 3.13 via `uv`, FastAPI, Pydantic v2, SQLAlchemy 2 (async) with
  asyncpg, Alembic, httpx, pytest with pytest-asyncio, Ruff, a strict type checker.
  `uv run` commands documented in `AGENTS.md`; a `Verify` line for the engine.
- **Deploy:** one more container in the production compose file, no published port,
  health check on `/healthz`; the 2 GB server plan still fits for early use. Caddy and
  Cloudflare are unchanged.

## 3. What happens to work already done

| Work | Fate |
|---|---|
| Homepage, waitlist, auth, deploy, backups (on `main`) | Unchanged |
| TypeScript AI gateway, `usage_event`, `ai_cache` (feature 2, on `main`) | Ported to Python (feature 31), parity-tested against the 45 existing test cases, then removed with a Drizzle migration |
| CV storage and extraction (feature 3a, parked branch) | Redone in the engine; the branch is kept until then for its tests, fixtures and review findings F-50 to F-56 |
| Provider choices and routing design | Carry over unchanged |

## 4. Build-plan changes (exact lines)

Add to Slice 1, after feature 2:

- [ ] 30. Python AI engine foundation - FastAPI service in `engine/` (uv, Pydantic, Ruff, strict typing, pytest), Dockerfile and compose entry, health and readiness, internal-only bearer auth with the user id from the verified web session, engine-owned Postgres schema with Alembic, TypeScript client in the web server, commands in AGENTS.md
- [ ] 31. Port the AI gateway and usage ledger to the engine - providers, tier routing, prompt versions, validated outputs, per-user cache and ledger in Python with parity tests, then remove the TypeScript gateway and its two tables

Replace feature 3 and its sub-items:

- [ ] 3. CV upload and parsing - in the engine: private storage, text extraction in a resource-limited subprocess, AI parse into a structured profile draft
  - [ ] 3a. CV storage, upload and text extraction - S3-compatible storage (RustFS locally), web upload route streaming to the engine, isolated extraction with memory, CPU and time limits and byte-counted decompression, CV record, owner-scoped signed download and delete
  - [ ] 3b. AI parse into a profile draft - background parse through the engine gateway into a structured draft (unconfirmed facts), upload and status screen, retry on failure

Extend feature 8 (append to its line): the golden-set runner is a Python command
(`uv run eval`) that prints a per-job report and a pass/fail against the founder's
verdicts, and is run before any model or prompt change ships.

Update the intro paragraph: "The stack is TypeScript for the web app and Python (FastAPI)
for the AI engine, over one Postgres."

Later (not scheduled), add: "Python job-source adapters (including Scrapling) in the engine
if scraping is ever approved within site terms."

## 5. Decisions I need from you

1. **Data boundary:** the engine owns AI-derived data (CV files, profile drafts,
   evaluations, kit documents). The profile review screen (feature 4) is built in
   TypeScript and calls engine endpoints. Agree?
2. **One Postgres, two schemas** (recommended), or a separate database for the engine?
3. **Python version and tooling:** 3.13 with `uv` (`uv` is already installed here; the
   system Python is 3.9). Agree?
4. **Interview artifacts:** do you want an architecture write-up and decision records
   (ADRs) kept in `docs/` as part of the work? I suggest yes, plus the eval report.

## 6. Edits made once you approve

- `blueprint/build-plan.md`: the lines in section 4.
- `blueprint/project-plan.md`: section 5 (stack and the "Decision" paragraph) and section 8
  (containers, env vars `ENGINE_URL` and `ENGINE_TOKEN`).
- `docs/technical-design.md`: modules, provider interfaces, deployment and security
  sections.
- `blueprint/context/project-overview.md`: regenerated with `/overview`.
- Parked feature 3a stays on its branch; feature 3 stays unchecked.

## 7. Effort and risk

- Features 30, 31 and 3a are each a normal feature cycle with an independent review;
  expect the engine foundation to take the longest because it sets the conventions.
- Risk: two services mean two test suites, two dependency sets and one more container.
  Mitigation: a single boundary rule, one internal API contract, and one `Verify`
  command that runs both suites.
- Python is new to you; I will keep the engine code small, typed and documented so it
  doubles as study material.
