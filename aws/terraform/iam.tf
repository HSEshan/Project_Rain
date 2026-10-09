# The instance's only credential. Nothing on the box holds an access key:
# boto3 in rest_api, the awslogs Docker driver and the AWS CLI in the deploy
# script all fetch short-lived credentials for this role from the instance
# metadata service.

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "${local.name}-app"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

# Session Manager (shell.sh) and Run Command (deploy-backend.sh). This is what
# replaces SSH.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "app" {
  # rest_api's S3 storage backend: write and delete uploaded images. Only
  # under media/, which is the only prefix CloudFront serves.
  statement {
    sid       = "MediaReadWrite"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.this["media"].arn}/media/*"]
  }

  # Pull release tarballs.
  statement {
    sid       = "ReleasesRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.this["artifacts"].arn}/releases/*"]
  }

  # The awslogs Docker driver, one stream per container. No CreateLogGroup:
  # the group is Terraform's, so a typo in a group name fails loudly instead of
  # creating a stray group with no retention.
  statement {
    sid = "ContainerLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["${aws_cloudwatch_log_group.app.arn}:*"]
  }

  # The SSM agent looks the group up before streaming Run Command output to it
  # (deploy-backend.sh). A list action, so it cannot be scoped to one group.
  statement {
    sid       = "FindLogGroup"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }

  # Configuration and secrets, read by the deploy script. The default
  # aws/ssm key decrypts SecureStrings without a separate KMS grant.
  statement {
    sid       = "Config"
    actions   = ["ssm:GetParametersByPath", "ssm:GetParameter", "ssm:GetParameters"]
    resources = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter${local.ssm_prefix}*"]
  }
}

resource "aws_iam_role_policy" "app" {
  name   = "${local.name}-app"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app.json
}

resource "aws_iam_instance_profile" "app" {
  name = "${local.name}-app"
  role = aws_iam_role.app.name
}
