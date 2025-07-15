#!/bin/bash

set -e

# Download GitHub Actions runner
VERSION="2.326.0"
FILE="actions-runner-linux-x64-${VERSION}.tar.gz"

if [ ! -d "./runner" ]; then
  curl -L -o ${FILE} https://github.com/actions/runner/releases/download/v${VERSION}/${FILE}
  tar xzf ${FILE}
  chmod +x ./config.sh ./run.sh ./env.sh
fi

# Configure runner
./config.sh --unattended \
  --url "${REPO_URL}" \
  --token "${RUNNER_TOKEN}" \
  --name "${RUNNER_NAME}" \
  --work "_work" \

# Run and remove after exit
exec ./run.sh
