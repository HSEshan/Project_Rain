#!/usr/bin/env bash
# Build the frontend locally and publish it to the frontend bucket.
#
#   aws/scripts/deploy-frontend.sh
#
# Vite inlines VITE_* values from frontend/.env at build time, the same file
# the VPS build uses (generate_env_files.py writes it).
#
# Caching, which is what makes a new deploy show up at once:
#   assets/*    content-hashed names, so cached for a year and never revalidated
#   index.html  no-cache: always revalidated, so it always names the new assets
#   the rest    five minutes (favicon and other unhashed public files)
# Then one invalidation for the paths that are not content-hashed.
source "$(dirname "$0")/lib.sh"
load_stack
require npm
FRONTEND_BUCKET="$(tf_out frontend_bucket)"
DISTRIBUTION_ID="$(tf_out cloudfront_distribution_id)"

cd "$REPO_ROOT/frontend"
[ -f .env ] || warn "frontend/.env is missing; the landing page links will be empty. Run generate_env_files.py."

log "npm ci"
npm ci --no-audit --no-fund

log "npm run build"
npm run build

dist="$(native_path "$PWD/dist")"
bucket="s3://$FRONTEND_BUCKET"

log "Uploading hashed assets"
aws s3 sync "$dist/assets" "$bucket/assets" --delete --only-show-errors \
  --cache-control "public, max-age=31536000, immutable"

log "Uploading everything else"
aws s3 sync "$dist" "$bucket" --delete --only-show-errors \
  --exclude "assets/*" --exclude "index.html" \
  --cache-control "public, max-age=300"
aws s3 cp "$dist/index.html" "$bucket/index.html" --only-show-errors \
  --cache-control "no-cache" --content-type "text/html; charset=utf-8"

log "Invalidating the unhashed paths"
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" \
  --paths "/" "/index.html" --query Invalidation.Id --output text >/dev/null

log "Frontend published"
echo "App: $(tf_out app_url)"
