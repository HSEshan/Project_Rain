# Three private buckets. None of them is public and none has a website
# endpoint: CloudFront reads the two that browsers need through Origin Access
# Control, and the third is only ever read by the instance.
#
# - media:     uploaded images, written by rest_api (STORAGE_BACKEND=s3) under
#              the `media/` prefix, served at /media/* by CloudFront
# - frontend:  the built SPA, synced by scripts/deploy-frontend.sh
# - artifacts: release tarballs, uploaded by scripts/deploy-backend.sh and
#              pulled by the instance
#
# `force_destroy` on all three, because this stack is built to be torn down:
# without it `terraform destroy` stops at the first non-empty bucket, and a half
# destroyed stack is exactly the thing that keeps billing. Do not copy it into a
# stack whose data matters.

locals {
  buckets = {
    media     = "${local.bucket_prefix}-media"
    frontend  = "${local.bucket_prefix}-frontend"
    artifacts = "${local.bucket_prefix}-artifacts"
  }
}

resource "aws_s3_bucket" "this" {
  for_each      = local.buckets
  bucket        = each.value
  force_destroy = true

  tags = { Name = each.value, Purpose = each.key }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each                = aws_s3_bucket.this
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Old releases are only useful for a rollback, and a week covers that.
resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.this["artifacts"].id

  rule {
    id     = "expire-releases"
    status = "Enabled"

    filter {
      prefix = "releases/"
    }

    expiration {
      days = 7
    }
  }
}

# CloudFront may read the two buckets browsers need, and only this
# distribution may: the SourceArn condition is what stops any other
# distribution, in any account, from using OAC to read them.
data "aws_iam_policy_document" "cloudfront_read" {
  for_each = toset(["media", "frontend"])

  statement {
    sid       = "CloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.this[each.key].arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.main.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "cloudfront_read" {
  for_each = data.aws_iam_policy_document.cloudfront_read
  bucket   = aws_s3_bucket.this[each.key].id
  policy   = each.value.json

  depends_on = [aws_s3_bucket_public_access_block.this]
}
