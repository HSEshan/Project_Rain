# One instance runs the same compose stack the VPS runs, minus the frontend
# container (CloudFront serves the bundle from S3) and, with use_rds, minus
# Postgres. It is the expensive part of the stack: stop it when not in use
# (scripts/stop.sh), and it costs only its disk and its address while stopped.

# Amazon Linux 2023, resolved at plan time from AWS's public SSM parameter so
# there is no AMI id to keep current by hand.
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-${var.architecture}"
}

resource "aws_instance" "app" {
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  # Needed during boot, before the Elastic IP below is attached: user data
  # installs packages, and without a public address and without a NAT gateway
  # the instance cannot reach anything. The EIP replaces it moments later.
  associate_public_ip_address = true

  # Burstable instances default to "unlimited", which bills for CPU beyond the
  # credit balance. On a stack left running it is a surprise line item; on
  # "standard" a busy instance slows down instead, and the CPU credit alarm in
  # cloudwatch.tf says so.
  credit_specification {
    cpu_credits = "standard"
  }

  metadata_options {
    # IMDSv2 only: a request needs a session token, which is what blocks the
    # SSRF-to-credentials attack IMDSv1 allowed.
    http_tokens = "required"
    # **Two hops, not the default one.** rest_api runs in a container on a
    # Docker bridge, which is one network hop further from the metadata
    # service than the host. With a hop limit of 1 its boto3 cannot fetch the
    # role's credentials, and uploads fail with NoCredentialsError while every
    # AWS CLI command on the host works fine.
    http_put_response_hop_limit = 2
    http_endpoint               = "enabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    encrypted             = true
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    region          = var.region
    ssm_prefix      = local.ssm_prefix
    compose_version = var.compose_version
    buildx_version  = var.buildx_version
  })

  tags = { Name = local.name }

  lifecycle {
    # A newer AMI or an edited bootstrap script must not replace a running
    # instance: without RDS, the database lives on this instance's disk.
    # Replace it deliberately with `terraform apply -replace=aws_instance.app`.
    ignore_changes = [ami, user_data]
  }
}

# A stable address, so CloudFront's origin and the ICE candidates LiveKit
# advertises survive a stop and start. Billed hourly like every public IPv4
# address, attached or not, which is why teardown.sh checks for loose ones.
resource "aws_eip" "app" {
  domain   = "vpc"
  instance = aws_instance.app.id

  tags = { Name = local.name }

  depends_on = [aws_internet_gateway.main]
}
