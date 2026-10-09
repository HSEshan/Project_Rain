# What can reach the instance, and from where.
#
# Port 80 is open to CloudFront and nothing else. The managed prefix list is
# AWS's own, kept current as CloudFront's addresses change; combined with the
# secret header Caddy checks (aws/Caddyfile.aws), it means the origin cannot be
# used to bypass the distribution, even by someone who finds its address.
#
# Gotcha worth knowing: that prefix list counts as ~55 rules against the
# security group's quota of 60, because it holds that many CIDR ranges. Adding a
# handful of other ingress rules to this group fails with a quota error that
# does not mention the prefix list at all.
#
# The LiveKit ports are open to the world because browsers connect to them
# directly. **7882/udp is voice.** A group that only opens web ports breaks
# voice in a way that looks like a client bug: the call connects (signalling
# goes through CloudFront) and then nobody hears anyone.

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "Project Rain instance: HTTP from CloudFront, LiveKit media from anywhere"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name}-app" }
}

resource "aws_vpc_security_group_ingress_rule" "http_from_cloudfront" {
  security_group_id = aws_security_group.app.id
  description       = "Caddy, only via CloudFront"
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

resource "aws_vpc_security_group_ingress_rule" "livekit_udp" {
  security_group_id = aws_security_group.app.id
  description       = "LiveKit WebRTC media (voice)"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "udp"
  from_port         = 7882
  to_port           = 7882
}

resource "aws_vpc_security_group_ingress_rule" "livekit_tcp" {
  security_group_id = aws_security_group.app.id
  description       = "LiveKit ICE/TCP fallback for networks that block UDP"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 7881
  to_port           = 7881
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.app.id
  description       = "Packages, images, AWS APIs, and media back to browsers"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# No SSH rule. Shell access is Session Manager (scripts/shell.sh): no open port,
# no key pair to lose, and every session is an IAM-authorised API call.

resource "aws_security_group" "db" {
  count       = var.use_rds ? 1 : 0
  name        = "${local.name}-db"
  description = "Postgres, from the app instance only"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name}-db" }
}

resource "aws_vpc_security_group_ingress_rule" "db_from_app" {
  count                        = var.use_rds ? 1 : 0
  security_group_id            = aws_security_group.db[0].id
  description                  = "Postgres from the app instance"
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
