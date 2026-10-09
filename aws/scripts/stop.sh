#!/usr/bin/env bash
# Stop paying for compute while keeping everything else.
#
#   aws/scripts/stop.sh
#
# Stops the instance (and the RDS database, if there is one). Data on the
# instance's disk survives a stop; so do the address and the CloudFront
# distribution, which then answer 502 until start.sh.
#
# What still bills while stopped: the EBS volume (~$2.40/month for 30 GB), the
# Elastic IP (~$3.60/month, AWS charges for every public IPv4 address), RDS
# storage, and pennies of S3. teardown.sh is what makes it zero.
#
# RDS gotcha: a stopped database starts itself again after 7 days, and bills
# from then on. AWS does this on purpose so patches get applied. Run stop.sh
# again, or teardown.sh, if it is going to sit longer than that.
source "$(dirname "$0")/lib.sh"
load_stack

log "Stopping instance $INSTANCE_ID"
aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --query 'StoppingInstances[0].CurrentState.Name' --output text

if [ "$(tf_out use_rds)" = "true" ]; then
  db_id="$(aws rds describe-db-instances \
    --query "DBInstances[?Endpoint.Address=='$(tf_out db_endpoint)'].DBInstanceIdentifier" --output text)"
  log "Stopping database $db_id (starts itself again after 7 days)"
  aws rds stop-db-instance --db-instance-identifier "$db_id" \
    --query DBInstance.DBInstanceStatus --output text || warn "Database was not running."
fi

aws ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
log "Stopped. aws/scripts/start.sh brings it back."
