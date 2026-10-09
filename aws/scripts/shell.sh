#!/usr/bin/env bash
# A root-capable shell on the instance, through Session Manager.
#
#   aws/scripts/shell.sh
#
# Needs the Session Manager plugin for the AWS CLI (README, Prerequisites).
# There is no SSH: port 22 is closed and the instance has no key pair. Each
# session is an IAM-authorised API call, logged in CloudTrail.
#
# Once in:  sudo -i; cd /opt/rain/current
#           docker compose -f docker-compose-prod.yml ps
source "$(dirname "$0")/lib.sh"
load_stack
command -v session-manager-plugin >/dev/null 2>&1 \
  || die "The Session Manager plugin is not installed (README, Prerequisites)."
aws ssm start-session --target "$INSTANCE_ID"
