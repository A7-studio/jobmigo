#!/bin/sh
# Apply migrations, then start the server. Fails loudly (and never prints the token).
set -eu

alembic upgrade head
exec uvicorn engine.main:create_app --factory --host 0.0.0.0 --port 8000 --no-access-log
