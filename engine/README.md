# Jobmigo engine

The internal Python service behind the web app. It will own everything that calls a
model or parses a file (the AI gateway and ledger, CV storage and extraction, parsing,
evaluation, the application kit). Today it is only the foundation: health checks, internal
auth, and its own database schema.

## How it fits

```
browser -> web (TanStack Start) --internal HTTP--> engine (FastAPI) -> Postgres schema "engine"
```

- The engine has **no public port**. The web server verifies the user's session, then calls the
  engine with `Authorization: Bearer <ENGINE_TOKEN>` and `X-User-Id: <uuid>`.
- Every error is `{ "code": ..., "message": ... }`, like the web app.
- Tables live in the Postgres schema `engine`, managed by Alembic. The web app's Drizzle
  migrations own the `public` schema. Neither touches the other's tables.

## Commands (run in `engine/`)

```bash
uv sync                                   # install Python 3.13 and dependencies
uv run --env-file ../.env pytest          # tests (needs Postgres running)
uv run ruff check .                       # lint
uv run ruff format .                      # format
uv run mypy                               # strict type check
uv run --env-file ../.env alembic upgrade head   # apply migrations to DATABASE_URL
uv run --env-file ../.env uvicorn engine.main:create_app --factory --port 8100
```

Environment (in the repo-root `.env`): `ENGINE_TOKEN` (at least 32 characters:
`openssl rand -hex 32`), `DATABASE_URL`, `ENGINE_TEST_DATABASE_URL` (a database whose name
ends in `_test`; tests refuse anything else), optional `LOG_LEVEL`.

## Layout

- `src/engine/main.py` - app factory (nothing runs on import)
- `src/engine/config.py` - settings; errors name variables, never values
- `src/engine/auth.py` - token and user id check
- `src/engine/errors.py`, `jsonlog.py`, `middleware.py` - stable errors, JSON logs, request ids
- `src/engine/db.py`, `models.py` - lazy async engine, the `engine` schema base class
- `migrations/` - Alembic (the schema is created by `env.py`; `0001_baseline` is empty)
- `tests/` - pytest (`tests/db.py` holds the `_test` database helpers)

## Rules

- Never log the token, user ids, headers or request bodies.
- Add a feature's tables as new Alembic revisions; never edit an applied one.
- Keep the code typed (`mypy --strict`) and small.
