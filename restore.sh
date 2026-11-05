#!/usr/bin/env bash
#
# Restore a Project Rain database, and optionally its uploaded images, from the
# files written by ./backup.sh.
#
#   ./restore.sh /opt/backups/project-rain/raindb-20260825T031500Z.sql.gz
#   ./restore.sh /opt/backups/project-rain/raindb-<stamp>.sql.gz \
#                /opt/backups/project-rain/media-<stamp>.tar
#   ./restore.sh --dev ./backups-dev/devdb-20260825T031500Z.sql.gz
#
# Pass the media archive with the same timestamp as the dump. Without one the
# images are left as they are, which is right when the volume survived and only
# the database did not.
#
# **This destroys the current database**, and the current images if an archive
# is given. A backup nobody has restored is a
# hope, not a backup, so this exists to be run — on the dev stack, deliberately,
# before it is ever needed in anger.
#
# What it does, in order:
#   1. stops the services that write (rest_api, ws_gateway), so nothing inserts
#      into a database that is being replaced underneath it
#   2. restores the dump, which begins with DROP statements (`pg_dump --clean`)
#   3. replaces the images, if an archive was given
#   4. starts the services again
#
# rest_api runs `alembic upgrade head` on startup, so a dump from an older
# schema is migrated forward on the way back up. A dump from a *newer* schema
# than the code is not: check out the matching commit first.

set -euo pipefail

DEV=false
if [ "${1:-}" = "--dev" ]; then
  DEV=true
  shift
fi

DUMP="${1:-}"
MEDIA="${2:-}"
if [ -z "$DUMP" ]; then
  echo "usage: ./restore.sh [--dev] <dump.sql.gz> [media.tar]" >&2
  exit 1
fi
if [ ! -f "$DUMP" ]; then
  echo "restore: $DUMP not found" >&2
  exit 1
fi
if [ -n "$MEDIA" ] && [ ! -f "$MEDIA" ]; then
  echo "restore: $MEDIA not found" >&2
  exit 1
fi

if [ "$DEV" = true ]; then
  COMPOSE="docker compose"
  ENV_FILE="postgres.dev.env"
else
  COMPOSE="docker compose -f docker-compose-prod.yml"
  ENV_FILE="postgres.env"
fi

# shellcheck disable=SC1090
set -a; . "./$ENV_FILE"; set +a
: "${POSTGRES_USER:?not set in $ENV_FILE}"
: "${POSTGRES_DB:?not set in $ENV_FILE}"

if ! gzip -t "$DUMP" 2>/dev/null; then
  echo "restore: $DUMP is not valid gzip" >&2
  exit 1
fi
# Checked before anything is touched, not when it is reached: finding out the
# archive is bad after the database has been replaced is the worst time.
if [ -n "$MEDIA" ] && ! tar -tf "$MEDIA" > /dev/null 2>&1; then
  echo "restore: $MEDIA is not a valid tar" >&2
  exit 1
fi

echo
echo "  About to REPLACE the contents of '$POSTGRES_DB'"
echo "  with $DUMP"
echo "  Everything currently in that database is lost."
if [ -n "$MEDIA" ]; then
  echo "  Every uploaded image is also replaced by $MEDIA"
fi
echo
# Typing the database name, not "y". This is the one command here that cannot
# be undone, and a habitual "y" is not a decision.
if [ "${RESTORE_YES:-}" != "$POSTGRES_DB" ]; then
  printf "  Type the database name to continue: "
  read -r CONFIRM
  if [ "$CONFIRM" != "$POSTGRES_DB" ]; then
    echo "restore: cancelled"
    exit 1
  fi
fi

echo "restore: stopping the services that write"
$COMPOSE stop rest_api ws_gateway

echo "restore: restoring"
# --clean --if-exists dumps drop each object before recreating it, so this does
# not need (and must not do) a DROP DATABASE: dropping the database would also
# take the role and extensions with it.
#
# ON_ERROR_STOP so a failed restore fails loudly instead of leaving a database
# that is half the backup and half whatever survived.
if ! gzip -cd "$DUMP" | $COMPOSE exec -T postgres \
      psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null; then
  echo "restore: FAILED. The database is in an unknown state." >&2
  echo "restore: the services are still stopped, on purpose." >&2
  exit 1
fi

if [ -n "$MEDIA" ]; then
  echo "restore: replacing uploaded images"
  # `run` rather than `exec`, because rest_api is stopped. Root because the
  # production image runs as appuser and tar has to restore ownership.
  #
  # Emptied first so the volume matches the dump. Images uploaded since the
  # backup would otherwise stay forever: no row names them, so the orphan sweep,
  # which works from rows, can never find them.
  if ! $COMPOSE run --rm --no-deps -T -u root rest_api \
        sh -c 'find /data/media -mindepth 1 -delete && tar -C /data/media -xf -' \
        < "$MEDIA"; then
    echo "restore: FAILED restoring images. The database is restored." >&2
    echo "restore: the services are still stopped, on purpose." >&2
    exit 1
  fi
fi

echo "restore: starting the services"
# rest_api migrates on startup, and ws_gateway waits for it to be healthy.
$COMPOSE start rest_api ws_gateway

TABLES="$($COMPOSE exec -T postgres psql -tAqU "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "select count(*) from information_schema.tables where table_schema='public'")"
USERS="$($COMPOSE exec -T postgres psql -tAqU "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "select count(*) from users" 2>/dev/null || echo "?")"

echo "restore: done. $TABLES tables, $USERS users."
echo "restore: check the app before trusting it."
