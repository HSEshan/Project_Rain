#!/usr/bin/env bash
# Shared by every script in aws/scripts. Sourced, not run.
#
# Works in bash on Linux and macOS and in Git Bash on Windows.

set -euo pipefail

AWS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC2034  # used by the scripts that source this file
REPO_ROOT="$(cd "$AWS_DIR/.." && pwd)"
TF_DIR="$AWS_DIR/terraform"
BUILD_DIR="$AWS_DIR/.build"

# Git Bash rewrites any argument that looks like a Unix path into a Windows
# one, so `--path /project-rain/poc` reaches the AWS CLI as
# `--path C:/Program Files/Git/project-rain/poc`. Every SSM parameter name
# and S3 key here starts with a slash; this turns the rewriting off.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!!  %s\033[0m\n' "$*" >&2; }
die() { printf '\033[1;31mxx  %s\033[0m\n' "$*" >&2; exit 1; }

require() {
  for tool in "$@"; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool is not installed (see aws/README.md, Prerequisites)"
  done
}

# A Terraform output, or a clear error if the stack has not been created.
tf_out() {
  tf output -raw "$1" 2>/dev/null \
    || die "No '$1' in Terraform outputs. Has scripts/up.sh been run?"
}

# terraform, run in aws/terraform. The path goes through native_path because
# the path rewriting disabled above is also what normally lets Windows
# terraform.exe understand a Git Bash path.
tf() {
  terraform -chdir="$(native_path "$TF_DIR")" "$@"
}

# Loads the outputs every script needs, once.
load_stack() {
  require terraform aws
  REGION="$(tf_out region)"
  INSTANCE_ID="$(tf_out instance_id)"
  LOG_GROUP="$(tf_out log_group)"
  export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"
}

# A Python that actually runs. On Windows `python3` is often the Microsoft
# Store stub, which exists on PATH and only prints an advert.
find_python() {
  for candidate in python python3; do
    if command -v "$candidate" >/dev/null 2>&1 \
      && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 8))' 2>/dev/null; then
      echo "$candidate"
      return
    fi
  done
  die "Python 3.8+ is needed (see aws/README.md, Prerequisites)"
}

# A path the AWS CLI can open. The CLI on Windows is a native program and does
# not understand Git Bash's /c/Users/... form.
native_path() {
  if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else echo "$1"; fi
}

confirm() {
  local answer
  read -r -p "$1 [y/N] " answer
  [ "$answer" = "y" ] || [ "$answer" = "Y" ]
}

# Run shell commands on the instance through SSM Run Command, wait, and print
# the output. Returns non-zero if the commands failed.
#
#   run_on_instance "description" "command 1" "command 2" ...
#
# SSM, not SSH: there is no port 22 open and no key pair (security.tf). Output
# is also streamed to CloudWatch, because the API truncates it at 24 KB and a
# first build is longer than that.
run_on_instance() {
  local comment="$1"; shift
  mkdir -p "$BUILD_DIR"
  local params="$BUILD_DIR/ssm-params.json"

  # Commands go through a JSON file so no shell has to survive a second layer
  # of quoting. python rather than jq because python is already a
  # prerequisite of the repo.
  "$(find_python)" - "$params" "$@" <<'PY'
import json, sys
path, commands = sys.argv[1], sys.argv[2:]
with open(path, "w") as f:
    json.dump({"commands": commands, "executionTimeout": ["3600"]}, f)
PY

  local command_id
  command_id="$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --comment "$comment" \
    --parameters "file://$(native_path "$params")" \
    --cloud-watch-output-config "CloudWatchOutputEnabled=true,CloudWatchLogGroupName=$LOG_GROUP" \
    --query Command.CommandId --output text)"
  rm -f "$params"

  echo "SSM command $command_id (full output: scripts/logs.sh $command_id)"
  local status="Pending"
  while [ "$status" = "Pending" ] || [ "$status" = "InProgress" ] || [ "$status" = "Delayed" ]; do
    sleep 10
    status="$(aws ssm get-command-invocation --command-id "$command_id" \
      --instance-id "$INSTANCE_ID" --query Status --output text 2>/dev/null || echo Pending)"
    printf '.'
  done
  echo

  aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" \
    --query StandardOutputContent --output text | tail -n 60
  if [ "$status" != "Success" ]; then
    aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" \
      --query StandardErrorContent --output text | tail -n 40 >&2
    die "Remote command finished with status $status"
  fi
}
