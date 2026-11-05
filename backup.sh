#!/usr/bin/env bash
#
# Nightly backup for Project Rain: a Postgres dump and the uploaded images.
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
#
# The two files belong together. Rows hold image *keys*, so a dump restored
# without its media archive brings back avatars and attachments whose files are
# gone. Restore a pair with the same timestamp.

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
# Media archives are full copies and grow with every upload, where a dump stays
# small, so they get their own and much shorter history. Keys are write-once, so
# the newest archive holds every image still in use anyway; the older ones only
# cover an image deleted by mistake.
MEDIA_KEEP="${MEDIA_KEEP:-7}"

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

# Rotates `<prefix>-*<suffix>` down to the newest $3. Only ever called after a
# new file has been written and checked: pruning first would mean a failing
# backup quietly eats the history it was meant to add to.
prune() {
  local prefix="$1" suffix="$2" keep="$3" count
  count="$(find "$BACKUP_DIR" -maxdepth 1 -name "${prefix}-*${suffix}" | wc -l)"
  if [ "$count" -gt "$keep" ]; then
    find "$BACKUP_DIR" -maxdepth 1 -name "${prefix}-*${suffix}" \
      | sort | head -n "$((count - keep))" \
      | while read -r old; do
          echo "backup: pruning $(basename "$old")"
          rm -f "$old"
        done
  fi
}

# Optional off-box copy. Set it to whatever you actually use; it runs once per
# file, with the file as $1:
#   OFFSITE_CMD='rsync -a "$1" backups@elsewhere:/srv/rain/'
#   OFFSITE_CMD='aws s3 cp "$1" s3://my-bucket/rain/'
offsite() {
  if [ -n "${OFFSITE_CMD:-}" ]; then
    echo "backup: copying $(basename "$1") off-box"
    bash -c "$OFFSITE_CMD" _ "$1"
  fi
}

offsite "$TARGET"
prune "$POSTGRES_DB" ".sql.gz" "$KEEP"

# Second, and in its own right: by now the dump is safely on disk, so a failure
# here must not cost it. It still exits non-zero, so cron reports it.
#
# Through rest_api because it is the service that mounts the volume read-write.
# A plain tar, not gzip: every file in it is already compressed WebP. With
# STORAGE_BACKEND=s3 the volume is empty and this writes an empty archive, which
# is correct: the bucket is the store then.
MEDIA_TARGET="$BACKUP_DIR/media-${STAMP}.tar"
MEDIA_PARTIAL="$MEDIA_TARGET.partial"

echo "backup: archiving uploaded images to $MEDIA_TARGET"
if ! $COMPOSE exec -T rest_api tar -C /data/media -cf - . > "$MEDIA_PARTIAL"; then
  rm -f "$MEDIA_PARTIAL"
  echo "backup: archiving media failed, the database dump above is unaffected" >&2
  exit 1
fi

# Unlike a dump, an archive with no files in it is a legitimate result: nobody
# has uploaded anything yet. So this checks that it is a tar, not that it is full.
if ! MEDIA_LIST="$(tar -tf "$MEDIA_PARTIAL")"; then
  rm -f "$MEDIA_PARTIAL"
  echo "backup: the media archive is not a valid tar" >&2
  exit 1
fi
MEDIA_FILES="$(printf '%s\n' "$MEDIA_LIST" | grep -c -v '/$' || true)"

mv "$MEDIA_PARTIAL" "$MEDIA_TARGET"
echo "backup: wrote $(du -h "$MEDIA_TARGET" | cut -f1) to $MEDIA_TARGET ($MEDIA_FILES files)"

offsite "$MEDIA_TARGET"
prune "media" ".tar" "$MEDIA_KEEP"

echo "backup: done, $(find "$BACKUP_DIR" -maxdepth 1 -name "${POSTGRES_DB}-*.sql.gz" | wc -l) dumps and $(find "$BACKUP_DIR" -maxdepth 1 -name "media-*.tar" | wc -l) media archives kept"
