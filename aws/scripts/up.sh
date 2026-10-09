#!/usr/bin/env bash
# Create or update the AWS stack (Terraform). Safe to re-run: it only changes
# what differs from aws/terraform/*.tf.
#
#   aws/scripts/up.sh            plan, confirm, apply
#   aws/scripts/up.sh -y         apply without the prompt
#
# First run takes 5 to 10 minutes, most of it CloudFront. With use_rds, add
# another 5 to 10 for the database.
source "$(dirname "$0")/lib.sh"
require terraform aws

[ -f "$TF_DIR/terraform.tfvars" ] \
  || die "Copy aws/terraform/terraform.tfvars.example to terraform.tfvars and set alert_email first."

log "Checking AWS credentials"
aws sts get-caller-identity --query '[Account, Arn]' --output text \
  || die "The AWS CLI has no working credentials. Run 'aws configure' or 'aws sso login'."

log "terraform init"
tf init -input=false -upgrade

log "terraform plan"
mkdir -p "$BUILD_DIR"
plan="$(native_path "$BUILD_DIR/up.tfplan")"
tf plan -input=false -out="$plan"

if [ "${1:-}" != "-y" ]; then
  confirm "Apply this plan? It creates billable resources." || die "Not applied."
fi

log "terraform apply"
tf apply -input=false "$plan"
rm -f "$BUILD_DIR/up.tfplan"

cat <<EOF

Stack is up.

  App:        $(tf_out app_url)   (empty until the first deploy)
  Dashboard:  $(tf_out dashboard_url)

Next:
  1. Confirm the SNS subscription mail sent to your alert address.
  2. aws/scripts/deploy.sh     build and ship the backend and the frontend
EOF
