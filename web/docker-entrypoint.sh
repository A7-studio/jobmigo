#!/bin/sh
# Apply database migrations, then start the server. If migrations fail the container
# exits and the server never starts.
set -e
# The waitlist rate limit may trust cf-connecting-ip only when Caddy rejects non-Cloudflare
# requests. Refuse the unsafe combination instead of silently running with it.
if [ "${TRUST_PROXY_HEADERS:-false}" = "true" ] && [ "${CLOUDFLARE_ONLY:-false}" != "true" ]; then
  echo "entrypoint: TRUST_PROXY_HEADERS=true requires CLOUDFLARE_ONLY=true; refusing to start" >&2
  exit 1
fi
node ./migrate/migrate.mjs
exec node .output/server/index.mjs
