data "aws_caller_identity" "current" {}

resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  name       = "${var.project}-${var.environment}"
  account_id = data.aws_caller_identity.current.account_id

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  # Everything the instance needs to know lives under this SSM path. The
  # instance reads it at deploy time (aws/instance/deploy-release.sh), which
  # keeps secrets out of user data, where anyone with ec2:DescribeInstanceAttribute
  # can read them in plain text.
  ssm_prefix = "/${var.project}/${var.environment}"

  # S3 bucket names are global across every AWS account, so a random suffix
  # keeps two people running this repo from colliding.
  bucket_prefix = "${local.name}-${random_id.suffix.hex}"
}
