# Everything the instance's deploy script needs, in Parameter Store. Standard
# parameters are free; Secrets Manager would be $0.40 a secret a month for
# rotation this stack does not use.
#
# Application secrets (JWT key, LiveKit secret, local Postgres password) are
# NOT here. They are generated on the instance by generate_env_files.py on the
# first deploy and never leave it, exactly as on the VPS. What lives here is
# only what Terraform itself creates or knows.

# Shared by CloudFront (sends it) and Caddy (requires it). An origin that
# answers anyone who finds its address is a way around every CloudFront
# setting, so this is the second lock after the security group.
resource "random_password" "origin_verify" {
  length  = 48
  special = false
}

resource "random_password" "db" {
  count = var.use_rds ? 1 : 0
  # RDS refuses /, @, " and space in a master password
  length  = 40
  special = false
}

locals {
  ssm_strings = merge(
    {
      "config/region"           = var.region
      "config/log_group"        = aws_cloudwatch_log_group.app.name
      "config/media_bucket"     = aws_s3_bucket.this["media"].bucket
      "config/artifacts_bucket" = aws_s3_bucket.this["artifacts"].bucket
      "config/use_rds"          = tostring(var.use_rds)
    },
    var.use_rds ? {
      "db/host" = aws_db_instance.main[0].address
      "db/name" = aws_db_instance.main[0].db_name
      "db/user" = aws_db_instance.main[0].username
    } : {}
  )

  ssm_secrets = merge(
    { "edge/origin_verify_secret" = random_password.origin_verify.result },
    var.use_rds ? { "db/password" = random_password.db[0].result } : {}
  )
}

resource "aws_ssm_parameter" "config" {
  for_each = local.ssm_strings
  name     = "${local.ssm_prefix}/${each.key}"
  type     = "String"
  value    = each.value
}

resource "aws_ssm_parameter" "secret" {
  # nonsensitive() on the keys only: the names are not secret, and for_each
  # refuses a sensitive collection outright.
  for_each = nonsensitive(toset(keys(local.ssm_secrets)))
  name     = "${local.ssm_prefix}/${each.key}"
  type     = "SecureString"
  value    = local.ssm_secrets[each.key]
}
