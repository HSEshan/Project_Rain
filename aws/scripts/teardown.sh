#!/usr/bin/env bash
# Delete the whole stack, then prove nothing billable is left.
#
#   aws/scripts/teardown.sh
#
# The deliverable of a proof of concept is knowing how it works and owing
# nothing afterwards (tasks.md, Phase 21). `terraform destroy` does the first
# half; the checks after it are the second, because "destroy said it finished"
# and "the bill is zero" are different claims:
#
#   - anything tagged Project=<project> that still exists
#   - Elastic IPs not attached to anything (billed hourly, easy to orphan)
#   - EBS volumes and snapshots from this stack
#   - the log group (it has retention, but it is still storage)
#
# Takes 10 to 20 minutes, most of it CloudFront disabling and deleting.
# **Irreversible**: uploaded images, the database and every message go with it.
source "$(dirname "$0")/lib.sh"
require terraform aws

if tf output -raw region >/dev/null 2>&1; then
  REGION="$(tf_out region)"
  PROJECT="$(tf_out project_tag)"
  NAME="$(tf_out name)"
else
  die "No Terraform state found in aws/terraform. Nothing to tear down from here."
fi
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"

cat <<EOF
This destroys $NAME in $REGION: the instance and its disk, the database,
all three buckets and everything in them, the CloudFront distribution, logs,
alarms and the budget. It cannot be undone.
EOF
confirm "Type y to destroy $NAME" || die "Nothing destroyed."

log "terraform destroy"
tf destroy -input=false -auto-approve

log "Verifying nothing is left"
leftovers=0

tagged="$(aws resourcegroupstaggingapi get-resources \
  --tag-filters "Key=Project,Values=$PROJECT" \
  --query 'ResourceTagMappingList[].ResourceARN' --output text)"
# CloudFront is global, and its tags are only visible from us-east-1.
# shellcheck disable=SC2016  # backticks are a JMESPath literal, not a subshell
tagged_global="$(aws resourcegroupstaggingapi get-resources --region us-east-1 \
  --tag-filters "Key=Project,Values=$PROJECT" \
  --query 'ResourceTagMappingList[?contains(ResourceARN, `cloudfront`)].ResourceARN' --output text)"
if [ -n "$tagged$tagged_global" ]; then
  warn "Still tagged Project=$PROJECT (the tagging index can lag deletion by a few minutes; re-run this check before worrying):"
  # shellcheck disable=SC2086  # split on purpose: one ARN per line
  printf '%s\n' $tagged $tagged_global
  leftovers=1
fi

loose_ips="$(aws ec2 describe-addresses \
  --query 'Addresses[?AssociationId==null].[AllocationId, PublicIp]' --output text)"
if [ -n "$loose_ips" ]; then
  warn "Unattached Elastic IPs in $REGION (these bill hourly):"
  echo "$loose_ips"
  leftovers=1
fi

volumes="$(aws ec2 describe-volumes --filters "Name=tag:Project,Values=$PROJECT" \
  --query 'Volumes[].VolumeId' --output text)"
snapshots="$(aws ec2 describe-snapshots --owner-ids self --filters "Name=tag:Project,Values=$PROJECT" \
  --query 'Snapshots[].SnapshotId' --output text)"
if [ -n "$volumes$snapshots" ]; then
  warn "EBS volumes or snapshots from this stack: $volumes $snapshots"
  leftovers=1
fi

groups="$(aws logs describe-log-groups --log-group-name-prefix "/$PROJECT/" \
  --query 'logGroups[].logGroupName' --output text)"
if [ -n "$groups" ]; then
  warn "Log groups still present: $groups"
  leftovers=1
fi

if [ "$leftovers" -eq 0 ]; then
  log "Clean. Nothing from $NAME remains in $REGION."
  echo "The budget alert is gone with it. Check the Billing console in a day or two; a partial day of charges is expected."
else
  die "Some resources remain. Delete them in the console, or re-run this script's checks in a few minutes."
fi
