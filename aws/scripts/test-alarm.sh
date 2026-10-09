#!/usr/bin/env bash
# Prove the alarm path works, end to end, with a real error line.
#
#   aws/scripts/test-alarm.sh
#
# Not `aws cloudwatch set-alarm-state`, which only proves that SNS can send
# mail. This writes an error-level JSON line through the same awslogs driver
# the services use, so it exercises every hop: container log -> CloudWatch
# Logs -> metric filter -> ErrorLogLines metric -> alarm -> SNS -> your inbox.
#
# Expect the ALARM mail within about five minutes, and the OK mail roughly
# five minutes after that. No mail at all usually means the SNS subscription
# was never confirmed.
source "$(dirname "$0")/lib.sh"
load_stack

log "Writing an error line into $LOG_GROUP from the instance"
run_on_instance "alarm test" \
  "docker run --rm --log-driver awslogs --log-opt awslogs-region=$REGION --log-opt awslogs-group=$LOG_GROUP --log-opt awslogs-stream=alarm-test --log-opt awslogs-create-group=false public.ecr.aws/docker/library/alpine:3.20 echo '{\"level\": \"error\", \"event\": \"alarm test from scripts/test-alarm.sh\"}'"

log "Watching the alarm (Ctrl+C to stop)"
alarm="$(tf_out name)-app-errors"
for _ in $(seq 1 40); do
  state="$(aws cloudwatch describe-alarms --alarm-names "$alarm" --query 'MetricAlarms[0].StateValue' --output text)"
  printf '%s  %s\n' "$(date +%H:%M:%S)" "$state"
  [ "$state" = "ALARM" ] && { log "Alarm fired. Check your inbox."; exit 0; }
  sleep 15
done
warn "Still not in ALARM after 10 minutes. Check the metric filter on the dashboard."
