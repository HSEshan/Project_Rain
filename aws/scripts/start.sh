#!/usr/bin/env bash
# Start what stop.sh stopped. The containers come back on their own: every
# service in docker-compose-prod.yml is `restart: unless-stopped`, and Docker
# is enabled at boot.
#
#   aws/scripts/start.sh
source "$(dirname "$0")/lib.sh"
load_stack

if [ "$(tf_out use_rds)" = "true" ]; then
  db_id="$(aws rds describe-db-instances \
    --query "DBInstances[?Endpoint.Address=='$(tf_out db_endpoint)'].DBInstanceIdentifier" --output text)"
  log "Starting database $db_id first, so the app finds it"
  aws rds start-db-instance --db-instance-identifier "$db_id" \
    --query DBInstance.DBInstanceStatus --output text || warn "Database was already running."
  aws rds wait db-instance-available --db-instance-identifier "$db_id"
fi

log "Starting instance $INSTANCE_ID"
aws ec2 start-instances --instance-ids "$INSTANCE_ID" --query 'StartingInstances[0].CurrentState.Name' --output text
aws ec2 wait instance-status-ok --instance-ids "$INSTANCE_ID"

log "Running. Containers take a minute more to pass their health checks."
echo "App: $(tf_out app_url)"
