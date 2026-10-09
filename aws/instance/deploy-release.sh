#!/usr/bin/env bash
# Bring the stack up from the release this script was extracted with.
#
# Runs ON THE INSTANCE, as root, through SSM Run Command, started by
# aws/scripts/deploy-backend.sh after it has unpacked the tarball into
# /opt/rain/releases/<id>. Output goes back to that script and to CloudWatch.
#
# Order matters and each step stops the deploy if it fails:
#   1. read configuration and secrets from SSM Parameter Store
#   2. generate the app's own secrets, first deploy only (generate_env_files.py)
#   3. point the env files at AWS (apply_overrides.py)
#   4. check_config.py, the same gate the VPS uses, before anything restarts
#   5. docker compose up --build
#   6. wait for health, then mark the release current
set -euo pipefail

release_dir="$(cd "$(dirname "$0")/../.." && pwd)"
release_id="$(basename "$release_dir")"
shared=/opt/rain/shared
python=python3.11

log() { printf '\n==> %s\n' "$*"; }

# shellcheck disable=SC1091
source /etc/project-rain/bootstrap.env
export AWS_REGION AWS_DEFAULT_REGION

if [ ! -f /etc/project-rain/bootstrap-complete ]; then
  echo "Instance bootstrap has not finished (see /var/log/project-rain-bootstrap.log)." >&2
  exit 1
fi

# --- 1. configuration ------------------------------------------------------------
log "Reading configuration from SSM ($RAIN_SSM_PREFIX)"
param() {
  aws ssm get-parameter --name "$RAIN_SSM_PREFIX/$1" --with-decryption \
    --query Parameter.Value --output text
}
RAIN_LOG_GROUP="$(param config/log_group)"
RAIN_MEDIA_BUCKET="$(param config/media_bucket)"
RAIN_USE_RDS="$(param config/use_rds)"
ORIGIN_VERIFY_SECRET="$(param edge/origin_verify_secret)"
export RAIN_MEDIA_BUCKET RAIN_USE_RDS

if [ "$RAIN_USE_RDS" = "true" ]; then
  RAIN_DB_HOST="$(param db/host)"
  RAIN_DB_NAME="$(param db/name)"
  RAIN_DB_USER="$(param db/user)"
  RAIN_DB_PASSWORD="$(param db/password)"
  export RAIN_DB_HOST RAIN_DB_NAME RAIN_DB_USER RAIN_DB_PASSWORD
fi

# --- 2. secrets, once ----------------------------------------------------------------
# The JWT key, the LiveKit secret and the local Postgres password are made
# here, on the instance, and never leave it. Regenerating them would sign
# everyone out and, without RDS, orphan the database volume, so this only runs
# when there are no env files yet.
if [ ! -f "$shared/rest_api.env" ]; then
  log "First deploy: generating application secrets"
  (cd "$shared" && "$python" -c \
    "import sys; sys.path.insert(0, '$release_dir'); import generate_env_files as g; g.main_prod()")
  chmod 600 "$shared"/*.env
fi

# --- 3. AWS specifics ------------------------------------------------------------
log "Applying AWS overrides"
"$python" "$release_dir/aws/instance/apply_overrides.py" "$shared"

# Compose resolves ./rest_api.env and ./livekit.yaml against the release
# directory; link them in rather than copying, so there is one copy of each
# secret on the disk.
for file in "$shared"/*.env "$shared/livekit.yaml"; do
  ln -sf "$file" "$release_dir/$(basename "$file")"
done

# Compose interpolation only, not container environment
umask 077
cat > "$shared/compose.env" <<EOF
AWS_REGION=$AWS_REGION
RAIN_LOG_GROUP=$RAIN_LOG_GROUP
ORIGIN_VERIFY_SECRET=$ORIGIN_VERIFY_SECRET
EOF
umask 022

# --- 4. the gate -----------------------------------------------------------------
log "Checking cross-service config"
(cd "$release_dir" && "$python" check_config.py --prod)

# --- 5. up ---------------------------------------------------------------------------
compose_files=(-f docker-compose-prod.yml -f aws/docker-compose.aws.yml)
if [ "$RAIN_USE_RDS" = "true" ]; then
  compose_files+=(-f aws/docker-compose.aws-rds.yml)
fi
compose() {
  (cd "$release_dir" && docker compose --env-file "$shared/compose.env" "${compose_files[@]}" "$@")
}

log "Building and starting release $release_id"
compose up -d --build --remove-orphans

# --- 6. healthy, then current ----------------------------------------------------------
log "Waiting for health checks"
# -a so a container that crashed on start (exited, restarting) is seen rather
# than silently missing from the list. Services with no health check report an
# empty health and pass on their state alone.
status() { compose ps -a --format '{{.Service}} {{.State}} {{.Health}}'; }
healthy=false
for _ in $(seq 1 60); do
  if ! status | grep -Eq ' (starting|unhealthy)$| (exited|restarting|dead|created)'; then
    healthy=true
    break
  fi
  sleep 5
done
compose ps -a

if [ "$healthy" != true ]; then
  echo "Services did not become healthy within 5 minutes. Logs: scripts/logs.sh" >&2
  exit 1
fi

ln -sfn "$release_dir" /opt/rain/current
log "Release $release_id is live"

# Keep the three newest releases for a quick look back; images and build
# cache are what actually fill the disk.
# shellcheck disable=SC2012  # release names are timestamps we generate
ls -1dt /opt/rain/releases/* | tail -n +4 | xargs -r rm -rf
docker image prune -f >/dev/null
docker builder prune -f --filter until=72h >/dev/null
df -h / | tail -n 1
