#!/usr/bin/env bash
# Nightly Postgres backup: pg_dump -> gzip -> age -> rclone remote. Run on the server
# from the repository checkout (the systemd timer does). Never prints secrets.
#
# Needs: docker compose, age, rclone. Settings come from deploy/.env.production or the
# environment: BACKUP_REMOTE (rclone path, e.g. r2:jobmigo-backups), AGE_RECIPIENT.
# Set ALLOW_UNENCRYPTED_BACKUP=true only for local testing.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
env_file="${ENV_FILE:-$here/.env.production}"
compose=(docker compose --env-file "$env_file" -f "$here/docker-compose.prod.yml")
RCLONE="${RCLONE:-rclone}"
AGE="${AGE:-age}"

get_var() { # read one KEY=value from the env file without sourcing it
  [ -f "$env_file" ] || return 0
  grep -E "^$1=" "$env_file" | tail -n1 | cut -d= -f2- || true
}

BACKUP_REMOTE="${BACKUP_REMOTE:-$(get_var BACKUP_REMOTE)}"
AGE_RECIPIENT="${AGE_RECIPIENT:-$(get_var AGE_RECIPIENT)}"
RETENTION="${BACKUP_RETENTION:-30d}"

log() { echo "backup: $*"; }
die() { echo "backup: $*" >&2; exit 1; }

[ -n "$BACKUP_REMOTE" ] || die "BACKUP_REMOTE is not set"
if [ -z "$AGE_RECIPIENT" ] && [ "${ALLOW_UNENCRYPTED_BACKUP:-false}" != "true" ]; then
  die "AGE_RECIPIENT is not set; backups contain personal data and must be encrypted"
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
if [ -n "$AGE_RECIPIENT" ]; then
  name="jobmigo-$stamp.sql.gz.age"
else
  name="jobmigo-$stamp.sql.gz"
  log "WARNING: writing an UNENCRYPTED backup (ALLOW_UNENCRYPTED_BACKUP=true)"
fi
target="${BACKUP_REMOTE%/}/$name"

cleanup_partial() { "$RCLONE" deletefile "$target" >/dev/null 2>&1 || true; }
trap cleanup_partial ERR

log "dumping the database to $name"
dump() { "${compose[@]}" exec -T db pg_dump -U jobmigo -d jobmigo --no-owner --clean --if-exists; }
if [ -n "$AGE_RECIPIENT" ]; then
  dump | gzip -9 | "$AGE" -r "$AGE_RECIPIENT" | "$RCLONE" rcat "$target"
else
  dump | gzip -9 | "$RCLONE" rcat "$target"
fi

listed="$("$RCLONE" lsf "$target")" || die "could not list the uploaded backup"
[ "$listed" = "$name" ] || die "uploaded backup not found on the remote"
size="$("$RCLONE" size --json "$target" | sed -n 's/.*"bytes":\([0-9]*\).*/\1/p')"
[ "${size:-0}" -gt 100 ] || die "uploaded backup is suspiciously small (${size:-0} bytes)"
trap - ERR

log "uploaded $name ($size bytes)"
"$RCLONE" delete "${BACKUP_REMOTE%/}" --min-age "$RETENTION" --include "jobmigo-*.sql.gz*"
log "removed backups older than $RETENTION"
