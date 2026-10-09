#!/usr/bin/env bash
# Ship the backend: package the repo, upload it to S3, and have the instance
# unpack and start it through SSM Run Command.
#
#   aws/scripts/deploy-backend.sh
#
# What gets packaged is the working tree as git sees it: tracked files plus
# untracked ones that are not ignored, **uncommitted edits included**. That is
# what you are testing, which is the point of a proof of concept. Everything
# gitignored stays behind, which is what keeps local env files, Terraform state
# and database dumps off the instance.
#
# The instance builds the images itself, like the VPS does. A first deploy
# takes 10 to 15 minutes on a t4g.small; later ones reuse the layer cache.
source "$(dirname "$0")/lib.sh"
load_stack
require git tar
ARTIFACTS_BUCKET="$(tf_out artifacts_bucket)"

cd "$REPO_ROOT"
release_id="$(date -u +%Y%m%d-%H%M%S)-$(git rev-parse --short HEAD)"
if [ -n "$(git status --porcelain)" ]; then
  release_id="$release_id-dirty"
  warn "Working tree has uncommitted changes; they are included in this release."
fi

log "Packaging release $release_id"
mkdir -p "$BUILD_DIR"
tarball="$BUILD_DIR/$release_id.tar.gz"
# -z on git ls-files and --null on tar, so a filename with a space survives.
# --ignore-failed-read because --cached still lists a tracked file you have
# deleted but not yet committed the deletion of.
git ls-files -z --cached --others --exclude-standard \
  | tar --null --ignore-failed-read -czf "$tarball" -T -
du -h "$tarball" | cut -f1

log "Uploading to s3://$ARTIFACTS_BUCKET/releases/"
aws s3 cp "$(native_path "$tarball")" "s3://$ARTIFACTS_BUCKET/releases/$release_id.tar.gz" --only-show-errors
rm -f "$tarball"

log "Deploying on $INSTANCE_ID"
dir="/opt/rain/releases/$release_id"
run_on_instance "deploy $release_id" \
  "set -euo pipefail" \
  "mkdir -p $dir" \
  "aws s3 cp s3://$ARTIFACTS_BUCKET/releases/$release_id.tar.gz /tmp/$release_id.tar.gz --region $REGION --only-show-errors" \
  "tar -xzf /tmp/$release_id.tar.gz -C $dir" \
  "rm -f /tmp/$release_id.tar.gz" \
  "bash $dir/aws/instance/deploy-release.sh"

log "Backend release $release_id is live"
echo "App: $(tf_out app_url)"
