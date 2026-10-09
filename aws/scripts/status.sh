#!/usr/bin/env bash
# What is running and whether it is healthy.
#
#   aws/scripts/status.sh
source "$(dirname "$0")/lib.sh"
load_stack

log "Instance"
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].[InstanceType, State.Name, PublicIpAddress]' --output text

if [ "$(tf_out use_rds)" = "true" ]; then
  log "Database"
  aws rds describe-db-instances \
    --query "DBInstances[?Endpoint.Address=='$(tf_out db_endpoint)'].[DBInstanceIdentifier, DBInstanceClass, DBInstanceStatus]" --output text
fi

log "Alarms"
aws cloudwatch describe-alarms --alarm-name-prefix "$(tf_out name)-" \
  --query 'MetricAlarms[].[AlarmName, StateValue]' --output text

state="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text)"
if [ "$state" = "running" ]; then
  log "Containers"
  run_on_instance "status" \
    "cd /opt/rain/current 2>/dev/null || { echo 'No release deployed yet'; exit 0; }" \
    "docker compose -f docker-compose-prod.yml ps -a --format 'table {{.Service}}\t{{.State}}\t{{.Health}}\t{{.Status}}'" \
    "df -h / | tail -n 1" \
    "free -m | head -n 2"
fi

log "Endpoints"
url="$(tf_out app_url)"
printf '%-8s %s\n' "App" "$url"
printf '%-8s %s\n' "Health" "$(curl -s -o /dev/null -w '%{http_code}' "$url/api/health" || echo unreachable)"
printf '%-8s %s\n' "Dash" "$(tf_out dashboard_url)"
