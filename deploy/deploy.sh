#!/usr/bin/env bash
# Deploy the latest commit on this server, or roll back to the previous good commit.
#   deploy.sh              pull, build, restart, wait for healthy; roll back on failure
#   deploy.sh --dry-run    print each command without running it
#   deploy.sh --rollback   redeploy the commit that was good before the current one
# Run from the repository checkout on the server. Needs deploy/.env.production.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
env_file="${ENV_FILE:-$here/.env.production}"
last_good_file="$here/.last-good-commit"
previous_good_file="$here/.previous-good-commit"
compose=(docker compose --env-file "$env_file" -f "$here/docker-compose.prod.yml")
timeout="${DEPLOY_HEALTH_TIMEOUT:-120}"

dry=false; rollback=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry=true ;;
    --rollback) rollback=true ;;
    *) echo "deploy: unknown option: $arg" >&2; exit 2 ;;
  esac
done

log() { echo "deploy: $*"; }
die() { echo "deploy: $*" >&2; exit 1; }
run() { echo "+ $*"; if ! $dry; then "$@"; fi; }

get_var() { grep -E "^$1=" "$env_file" | tail -n1 | cut -d= -f2- || true; }

[ -f "$env_file" ] || die "$env_file not found (copy deploy/.env.production.example and fill it in)"

# The database password goes into a URL, so it must be URL-safe (openssl rand -hex 24).
password="$(get_var POSTGRES_PASSWORD)"
[ -n "$password" ] || die "POSTGRES_PASSWORD is empty"
[[ "$password" =~ ^[A-Za-z0-9._~-]+$ ]] || die "POSTGRES_PASSWORD must use only letters, digits and . _ ~ - (generate one with: openssl rand -hex 24)"

# The waitlist rate limit may trust Cloudflare's header only when direct requests are refused.
if [ "$(get_var TRUST_PROXY_HEADERS)" = "true" ] && [ "$(get_var CLOUDFLARE_ONLY)" != "true" ]; then
  die "TRUST_PROXY_HEADERS=true requires CLOUDFLARE_ONLY=true"
fi

if ! $dry && [ -n "$(git -C "$root" status --porcelain)" ]; then
  die "the checkout has local changes; commit or discard them first"
fi

web_health() {
  local id
  id="$("${compose[@]}" ps -q web 2>/dev/null || true)"
  [ -n "$id" ] || { echo "missing"; return; }
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id"
}

wait_healthy() {
  $dry && { log "would wait up to ${timeout}s for the web container to be healthy"; return 0; }
  local waited=0 status="unknown"
  while [ "$waited" -lt "$timeout" ]; do
    status="$(web_health)"
    [ "$status" = "healthy" ] && return 0
    sleep 3; waited=$((waited + 3))
  done
  log "web container is '$status' after ${timeout}s"
  return 1
}

start_stack() {
  run "${compose[@]}" up -d --build || return 1
  # Pick up Caddy config or Cloudflare range changes without recreating the container.
  run "${compose[@]}" exec -T caddy caddy reload --config /etc/caddy/Caddyfile || return 1
  wait_healthy
}

before="$(git -C "$root" rev-parse HEAD)"

if $rollback; then
  [ -f "$previous_good_file" ] || die "no previous good commit recorded; deploy at least twice first"
  target="$(cat "$previous_good_file")"
  log "rolling back to $target"
  run git -C "$root" reset --hard "$target"
else
  log "current commit: $before"
  run git -C "$root" pull --ff-only
fi

current="$(git -C "$root" rev-parse HEAD)"
if start_stack; then
  if $dry; then log "dry run finished; nothing was changed"; exit 0; fi
  if $rollback; then
    echo "$current" > "$last_good_file"
  else
    # Remember the good commit before this one so --rollback has somewhere to go.
    if [ -f "$last_good_file" ] && [ "$(cat "$last_good_file")" != "$current" ]; then
      cp "$last_good_file" "$previous_good_file"
    fi
    echo "$current" > "$last_good_file"
  fi
  log "deployed commit $current"
  "${compose[@]}" exec -T web node -e "fetch('http://127.0.0.1:3000/readyz').then(r=>r.text()).then(t=>console.log('deploy: readyz', t))"
  exit 0
fi

log "the new version did not become healthy"
if [ "$current" != "$before" ]; then
  log "restoring previous commit $before"
  run git -C "$root" reset --hard "$before"
  if start_stack; then log "previous version is running again"; else log "WARNING: the previous version is not healthy either; check the logs"; fi
fi
exit 1
