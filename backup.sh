#!/usr/bin/env bash
#
# Nightly Postgres dump for Project Rain.
#
# There is real user data in the postgres volume — accounts, friendships, every
# message — and until this existed there was no copy of any of it. One `docker
# volume rm` or one bad migration and it was gone.
#
#   ./backup.sh                 # prod (docker-compose-prod.yml, postgres.env)
#   ./backup.sh --dev           # the dev stack, for testing this script
#   BACKUP_DIR=/mnt/x ./backup.sh
#
# Install as a cron job (see DEPLOY.md, "Backups"):
#   15 3 * * * cd /opt/apps/project-rain && ./backup.sh >> /var/log/rain-backup.log 2>&1
#
# **A dump on the same disk is not a backup.** It survives a dropped table, a
# bad migration and a deleted volume; it does not survive losing the machine.
# Copying the file off the box is a decision with a cost (where to, who pays,
# what it means for the data) and is left to whoever runs this. `OFFSITE_CMD`
# below is the hook.

set -euo pipefail

DEV=false
[ "${1:-}" = "--dev" ] && DEV=true

if [ "$DEV" = true ]; then
  COMPOSE="docker compose"
  ENV_FILE="postgres.dev.env"
  BACKUP_DIR="${BACKUP_DIR:-./backups-dev}"
else
  COMPOSE="docker compose -f docker-compose-prod.yml"
  ENV_FILE="postgres.env"
  BACKUP_DIR="${BACKUP_DIR:-/opt/backups/project-rain}"
fi

# How many dumps to keep. At one a night this is a month of history; each is a
# few hundred kilobytes gzipped at this size.
KEEP="${KEEP:-30}"

if [ ! -f "$ENV_FILE" ]; then
  echo "backup: $ENV_FILE not found. Run this from the repository root." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; . "./$ENV_FILE"; set +a
: "${POSTGRES_USER:?not set in $ENV_FILE}"
: "${POSTGRES_DB:?not set in $ENV_FILE}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/${POSTGRES_DB}-${STAMP}.sql.gz"
PARTIAL="$TARGET.partial"

echo "backup: dumping $POSTGRES_DB to $TARGET"

# Written to .partial and renamed only on success, so a dump interrupted
# half-way never sits in the directory looking like a usable backup. `set -o
# pipefail` above is what makes a pg_dump failure fail the pipeline rather than
# being hidden by gzip exiting 0.
if ! $COMPOSE exec -T postgres pg_dump \
      -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
      | gzip -9 > "$PARTIAL"; then
  rm -f "$PARTIAL"
  echo "backup: pg_dump failed" >&2
  exit 1
fi

# A dump of nothing is the failure mode that looks like success: pg_dump can
# exit 0 having written only its header if the database is empty or the wrong
# one was named.
if ! gzip -t "$PARTIAL" 2>/dev/null; then
  rm -f "$PARTIAL"
  echo "backup: the dump is not valid gzip" >&2
  exit 1
fi
# Deliberately `grep -c` and not `grep -q`. Under `set -o pipefail`, `grep -q`
# exits at the first match, closes the pipe, and the decompressor dies of
# SIGPIPE — which pipefail then reports as a failed pipeline, so a perfectly
# good dump is thrown away. That is not hypothetical; it is what this script
# did the first time it was run.
TABLE_COUNT="$(gzip -cd "$PARTIAL" | grep -c "CREATE TABLE" || true)"
if [ "$TABLE_COUNT" -eq 0 ]; then
  rm -f "$PARTIAL"
  echo "backup: the dump contains no tables, refusing to keep it" >&2
  exit 1
fi

mv "$PARTIAL" "$TARGET"
echo "backup: wrote $(du -h "$TARGET" | cut -f1) to $TARGET ($TABLE_COUNT tables)"

# Optional off-box copy. Set it to whatever you actually use:
#   OFFSITE_CMD='rsync -a "$1" backups@elsewhere:/srv/rain/'
#   OFFSITE_CMD='aws s3 cp "$1" s3://my-bucket/rain/'
if [ -n "${OFFSITE_CMD:-}" ]; then
  echo "backup: copying off-box"
  bash -c "$OFFSITE_CMD" _ "$TARGET"
fi

# Prune last, and only after a new dump has been written and checked. Doing it
# first would mean a failing backup quietly eats the history it was meant to
# add to.
COUNT="$(find "$BACKUP_DIR" -maxdepth 1 -name "${POSTGRES_DB}-*.sql.gz" | wc -l)"
if [ "$COUNT" -gt "$KEEP" ]; then
  find "$BACKUP_DIR" -maxdepth 1 -name "${POSTGRES_DB}-*.sql.gz" \
    | sort | head -n "$((COUNT - KEEP))" \
    | while read -r old; do
        echo "backup: pruning $(basename "$old")"
        rm -f "$old"
      done
fi

echo "backup: done, $(find "$BACKUP_DIR" -maxdepth 1 -name "${POSTGRES_DB}-*.sql.gz" | wc -l) kept"
