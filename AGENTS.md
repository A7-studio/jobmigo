# AGENTS.md

Instructions for AI coding agents working in this project. This is the cross-tool
entry point. Codex, Google Antigravity, and OpenCode read `AGENTS.md`. Other
compatible tools do too. Claude Code reads `CLAUDE.md`, which imports this file,
so there is a single source of truth.

Claude Code, Codex, and every other AI tool must not add AI attribution to
commits or pull requests, including AI `Co-Authored-By` trailers or generated-by
signatures. Preserve genuine human attribution. See
[Commit and PR attribution](blueprint/context/ai-interaction.md#commit-and-pr-attribution)
for optional tool settings.

## What this is

A description of your project and the problem it solves.

This project is built with the **AI Blueprint**, a workflow layer, not an
app skeleton. To start a new project, scaffold the app first in an empty folder
(create-next-app, Vite, etc.), then overlay these files on top. Never run a
framework scaffolder inside a directory that already holds the blueprint files
(`AGENTS.md`, `CLAUDE.md`, `.agents/`, `.claude/`, `blueprint/`); it fails
because the directory isn't empty.

The workflow is defined by the local skills and context files below.

## Proportional engineering

Build for established requirements, not hypothetical scale, threats, or future
flexibility. Reuse existing code, the standard library, native platform features,
and installed dependencies before adding machinery.

- Unknown scale or extensibility defaults to the smaller reversible design. Do
  not infer enterprise, multi-tenant, hostile-user, or compliance requirements.
- Derive trust and data-integrity boundaries from actual reachability: untrusted
  input, auth/session/ownership, shared persisted data, destructive operations,
  payments, secrets, and sensitive data.
- Ask only when an unknown materially changes behavior, architecture, persisted
  data, interoperability, a real security boundary, or cost. Otherwise choose the
  simplest repository-native implementation.
- Add an abstraction, dependency, service, configuration surface, compatibility
  layer, or security mechanism only for a current requirement.
- Simplicity never removes real trust-boundary validation, data-loss prevention,
  accessibility, explicit security requirements, configured tests, or project rules.
- Stack-specific template standards apply only when the project uses that stack.

## Read these when relevant

- `blueprint/config.json` - deterministic project workflow settings
- `blueprint/workflow.md` - workflow reference for configuration, skills, dashboard activity, and checks
- `blueprint/context/project-overview.md` - the project's source of truth
- `blueprint/context/coding-standards.md` - read before changing code
- `blueprint/context/ai-interaction.md` - read when running the Blueprint workflow
- `blueprint/context/current-feature.md` - the one feature, fix, or rollback being built in this checkout

Reuse relevant context already loaded in the session. Claude Code imports only
this file; its Blueprint skills load the other files on demand.

## Workflow

Build one feature, fix, or rollback at a time, behind review gates. The feature
loop is `/feature` -> `/implement` -> `/check` -> `/audit current` ->
`/complete`; approve the Feature spec before Implement. Each command is a local
skill at `.agents/skills/<skill>/SKILL.md` or `.claude/skills/<skill>/SKILL.md`
that carries its own instructions. Claude Code and Google Antigravity use slash
commands such as `/feature`, Codex uses `$feature`, and other tools can follow
the matching `SKILL.md` when asked.

Skills: `adopt`, `audit`, `blueprint-doctor`, `blueprint-status`, `brief`,
`check`, `ci`, `complete`, `debug`, `discovery`, `explore`, `feature`, `fix`,
`implement`, `onboard`, `overview`, `prototype`, `release`, `rollback`, and
`tests`, plus the explicit-only `autopilot` and `continuous`.

- Keep one active work item per checkout. Parallel work needs its own clone or
  Git worktree and branch; never replace another worker's active spec.
- `blueprint/config.json` can make review or verification stricter and tune
  local workflow settings. It never grants permission to commit, merge, push,
  deploy, publish, send, delete data, waive a failing check, or accept a finding.
- Never create or edit `blueprint/.state/run.json` directly. Tracked skills
  record dashboard activity through the managed helper.

## Commands

Jobmigo is two services over one PostgreSQL: a TypeScript app, TanStack Start (`web/`) with
the server code, Better Auth and Drizzle, and a Python AI engine (`engine/`, FastAPI, uv).
Local ports: web 3000, Postgres 5442, engine 8100 (this machine only).
Copy `.env.example` to `.env` first (the scripts below read it).

Run these in `web/` unless noted:

- Database: `docker compose up -d db` (repo root)
- Database reset (deletes local data): `docker compose down -v` then `docker compose up -d db` (repo root), then `npm run db:migrate`
- Migrate: `npm run db:migrate`; new migration after a schema change: `npm run db:generate`
- Dev server: `npm run dev` (http://localhost:3000, health at `/healthz`, `/readyz`)
- Build: `npm run build`
- Lint: `npm run lint`
- Type check: `npm run typecheck`
- Test: `npm test` (Vitest; needs the database running; uses `TEST_DATABASE_URL`, whose name must end in `_test`)
- Waitlist: with `RESEND_API_KEY` unset and `ENVIRONMENT=local`, the confirmation email is printed to the dev server log (grep for `console provider`). See signups: `docker compose exec db psql -U jobmigo -d jobmigo -c "select email, status, source, created_at from waitlist_signup order by created_at"`
- Object storage (CVs, in the engine): `docker compose up -d storage` (RustFS; S3 API on http://localhost:9100, console on 9101, local credentials in `.env.example`). Adapter tests: `STORAGE_LIVE_TEST=1 uv run --env-file ../.env pytest tests/test_storage_live.py` in `engine/`
- CV extraction memory limits (Linux only, because macOS does not enforce `RLIMIT_AS`): from the repo root run `docker run --rm -v "$PWD/engine":/src:ro -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e UV_LINK_MODE=copy python:3.13-slim sh -c 'pip install -q uv==0.13.6 && cp -r /src /app && cd /app && rm -rf .venv && uv sync --frozen -q && uv run --frozen pytest tests/test_cv_limits_linux.py tests/test_cv_runner.py -q -p no:cacheprovider'`. On macOS those tests are skipped
- CV parse live check (engine): with `AI_CHEAP_MODEL` and its provider key in `.env`, in `engine/` run `AI_LIVE_TEST=1 uv run --env-file ../.env pytest tests/test_cv_parse_live.py` (one real call with a synthetic CV; skipped otherwise)
- AI gateway (engine): set `AI_CHEAP_MODEL` (and its provider key) in `.env`, then in `engine/` run `AI_LIVE_TEST=1 uv run --env-file ../.env pytest tests/test_ai_live.py` to make one real call and check the usage ledger. Without `AI_LIVE_TEST=1` that test is skipped
- Production: `npm run build` then `npm start` (Node, `.output/server/index.mjs`). Server deploy, backups and rollback live in `deploy/` and are explained in `docs/deploy.md` (`deploy/deploy.sh`, `deploy/backup.sh`, `deploy/restore.sh`)
- Verify: `(cd web && npm run lint && npm run typecheck && npm run build && npm test) && (cd engine && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run --env-file ../.env pytest)`
- Engine (run in `engine/`; needs `uv`, which installs Python 3.13 itself, and the database running): `uv sync` once, then `uv run --env-file ../.env pytest`, `uv run ruff check .`, `uv run ruff format .`, `uv run mypy`. Start it on its own with `docker compose up -d --build engine` (repo root; port 8100) or `uv run --env-file ../.env uvicorn engine.main:create_app --factory --port 8100`. Set `ENGINE_TOKEN` (at least 32 characters, `openssl rand -hex 32`), `ENGINE_URL` and `ENGINE_TEST_DATABASE_URL` in `.env`. Live client check: `ENGINE_LIVE_TEST=1 npm test -- tests/engine-live.test.ts` in `web/`
- Full local stack: `docker compose up --build` (development image `web/Dockerfile.dev`; the production image is `web/Dockerfile`)

Browser testing is opt-in. Run `/tests browser` or `$tests browser` to add or
normalize a browser harness and document its exact command as `Browser
tests`. Check and Continuous Mode can then reuse it without installing tooling
mid-feature.
