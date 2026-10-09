#!/usr/bin/env bash
# Ship everything: backend, then frontend. Backend first, so a frontend that
# expects a new API never goes live in front of the old one.
#
#   aws/scripts/deploy.sh
set -euo pipefail
here="$(dirname "$0")"
# Through bash rather than executed directly, so this works whether or not the
# executable bit survived the checkout (Windows does not record it).
bash "$here/deploy-backend.sh"
bash "$here/deploy-frontend.sh"
