#!/usr/bin/env bash
# Restore a backup made by backup.sh.
#   restore.sh <backup file or object name> [--into-live]
# The backup is always restored into a NEW scratch database first (jobmigo_restore_<time>)
# in a single transaction, so a bad file or a wrong key changes nothing that matters.
# With --into-live, after that succeeds, the scratch database is swapped in for the live
# one by renaming; the old live database is kept as jobmigo_before_restore_<time>.
# --into-live needs the web container stopped and a typed confirmation. For .age files set
# AGE_IDENTITY_FILE to the private key (kept off the server; see docs/deploy.md).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
env_file="${ENV_FILE:-$here/.env.production}"
compose=(docker compose --env-file "$env_file" -f "$here/docker-compose.prod.yml")
RCLONE="${RCLONE:-rclone}"
AGE="${AGE:-age}"

die() { echo "restore: $*" >&2; exit 1; }
get_var() { [ -f "$env_file" ] || return 0; grep -E "^$1=" "$env_file" | tail -n1 | cut -d= -f2- || true; }

source_arg="${1:-}"; mode="${2:-}"
[ -n "$source_arg" ] || die "usage: restore.sh <backup file or object name> [--into-live]"
[ -z "$mode" ] || [ "$mode" = "--into-live" ] || die "unknown option: $mode"
BACKUP_REMOTE="${BACKUP_REMOTE:-$(get_var BACKUP_REMOTE)}"

psql_db() { # psql_db <database> [extra psql flags]; SQL comes from stdin
  local db="$1"; shift
  "${compose[@]}" exec -T db psql -v ON_ERROR_STOP=1 -q -U jobmigo -d "$db" "$@"
}

# --- Checks that must pass before anything is touched --------------------------------
case "$source_arg" in
  *.age)
    [ -n "${AGE_IDENTITY_FILE:-}" ] && [ -f "$AGE_IDENTITY_FILE" ] || die "set AGE_IDENTITY_FILE to your age private key file"
    ;;
esac

if [ "$mode" = "--into-live" ]; then
  web_id="$("${compose[@]}" ps -q web 2>/dev/null || true)"
  if [ -n "$web_id" ] && [ "$(docker inspect --format '{{.State.Running}}' "$web_id")" = "true" ]; then
    die "the web container is running; stop it first: docker compose ... stop web"
  fi
  echo "This will REPLACE the live database with this backup (the old one is kept under another name)."
  read -r -p "Type 'replace live database' to continue: " answer
  [ "$answer" = "replace live database" ] || die "not confirmed; nothing was changed"
fi

fetch() {
  if [ -f "$source_arg" ]; then cat "$source_arg"
  else [ -n "$BACKUP_REMOTE" ] || die "BACKUP_REMOTE is not set"; "$RCLONE" cat "${BACKUP_REMOTE%/}/$source_arg"; fi
}
decrypt() {
  case "$source_arg" in
    *.age) "$AGE" -d -i "$AGE_IDENTITY_FILE" ;;
    *) cat ;;
  esac
}

# --- Restore into a scratch database (the live one is not touched yet) ----------------
stamp="$(date -u +%Y%m%d%H%M%S)"
scratch="jobmigo_restore_$stamp"
psql_db postgres <<< "create database \"$scratch\" owner jobmigo;" >/dev/null
if ! { fetch | decrypt | gunzip | psql_db "$scratch" -1 >/dev/null; }; then
  psql_db postgres <<< "drop database if exists \"$scratch\";" >/dev/null || true
  die "restore failed; the scratch database was removed and nothing else was changed"
fi
tables="$(psql_db "$scratch" -t -A <<< "select count(*) from information_schema.tables where table_schema = 'public';")"
[ "${tables:-0}" -gt 0 ] || { psql_db postgres <<< "drop database if exists \"$scratch\";" >/dev/null || true; die "the backup restored no tables; nothing was changed"; }

if [ "$mode" != "--into-live" ]; then
  echo "restore: restored into database $scratch ($tables tables). Drop it when you are done:"
  echo "  docker compose ... exec -T db psql -U jobmigo -d postgres -c 'drop database \"$scratch\"'"
  exit 0
fi

# --- Swap the verified scratch database in for the live one ---------------------------
old="jobmigo_before_restore_$stamp"
psql_db postgres <<< "select pg_terminate_backend(pid) from pg_stat_activity where datname in ('jobmigo', '$scratch') and pid <> pg_backend_pid(); alter database jobmigo rename to \"$old\"; alter database \"$scratch\" rename to jobmigo;" >/dev/null
echo "restore: the live database was replaced. The previous one is kept as $old."
echo "restore: start the web container again, check the site, then drop $old when you are sure."
