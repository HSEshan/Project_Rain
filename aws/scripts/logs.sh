#!/usr/bin/env bash
# Tail the stack's logs from CloudWatch.
#
#   aws/scripts/logs.sh                  every container, following
#   aws/scripts/logs.sh rest_api         one service (stream names contain it)
#   aws/scripts/logs.sh <ssm-command-id> the full output of one deploy
#
# Streams are named after the container ("project-rain-rest_api-1") and SSM
# command output lands in the same group, under the command id.
source "$(dirname "$0")/lib.sh"
load_stack

filter="${1:-}"
if [ -z "$filter" ]; then
  aws logs tail "$LOG_GROUP" --follow --since 15m --format short
elif [[ "$filter" =~ ^[0-9a-f-]{36}$ ]]; then
  aws logs tail "$LOG_GROUP" --log-stream-name-prefix "$filter" --since 1d --format short
else
  aws logs tail "$LOG_GROUP" --follow --since 15m --format short \
    --log-stream-name-prefix "project-rain-$filter"
fi
