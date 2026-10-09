# One distribution is the whole public face of the app, and it routes by path:
#
#   /api/*  /ws*  /livekit/*   -> the instance (Caddy), never cached
#   /media/*                   -> the media bucket, cached
#   everything else            -> the frontend bucket, cached, SPA rewrite
#
# **One hostname is the design decision.** The browser app assumes it lives on
# the same origin as /api, /ws and /livekit: the refresh cookie is scoped to
# /api/auth, and nothing sends CORS headers. Serving the bundle from one host
# and the API from another would mean reworking cookies and adding CORS to buy
# nothing. Path routing keeps the app unchanged, and it also means the stack
# needs no domain of its own: CloudFront's *.cloudfront.net certificate covers
# it.
#
# The tradeoff, from tasks.md: this puts the chat websocket and LiveKit
# signalling behind CloudFront, which that note said not to do without
# measuring. It is done because the alternative is the cross-origin rework
# above; README "Measuring the websocket path" is how to measure it. Voice
# *media* never touches CloudFront either way: it is UDP to the instance.

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

# Forwards every header, cookie and query string except Host. The API needs
# Authorization and the refresh cookie; the websocket upgrade needs its
# Sec-WebSocket-* headers; /ws needs ?token=.
data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

# HSTS, nosniff, frame-options, referrer-policy. nosniff matters most on
# /media: a browser must never guess that an image is something else.
data "aws_cloudfront_response_headers_policy" "security" {
  name = "Managed-SecurityHeadersPolicy"
}

resource "aws_cloudfront_origin_access_control" "s3" {
  name                              = "${local.name}-s3"
  description                       = "Signed reads from the private buckets"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "${local.name}-spa-rewrite"
  runtime = "cloudfront-js-2.0"
  comment = "Serve index.html for client-side routes"
  publish = true
  code    = file("${path.module}/functions/spa-rewrite.js")
}

locals {
  app_paths = ["/api/*", "/ws*", "/livekit/*"]
}

resource "aws_cloudfront_distribution" "main" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = local.name
  price_class     = var.cloudfront_price_class
  aliases         = var.domain_name == "" ? [] : [var.domain_name]

  origin {
    origin_id                = "frontend"
    domain_name              = aws_s3_bucket.this["frontend"].bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }

  origin {
    origin_id                = "media"
    domain_name              = aws_s3_bucket.this["media"].bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }

  origin {
    origin_id = "app"
    # CloudFront needs a DNS name, not an IP. The EIP's public DNS name
    # resolves to it and stays stable across stop/start.
    domain_name = aws_eip.app.public_dns

    custom_origin_config {
      http_port  = 80
      https_port = 443
      # CloudFront to the instance is plain HTTP inside AWS's network; the
      # browser to CloudFront is HTTPS. Encrypting the second hop too needs a
      # certificate on the instance, which needs a domain. README covers it.
      origin_protocol_policy   = "http-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 60
      origin_keepalive_timeout = 60
    }

    custom_header {
      name  = "X-Origin-Verify"
      value = random_password.origin_verify.result
    }
  }

  default_cache_behavior {
    target_origin_id           = "frontend"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }
  }

  ordered_cache_behavior {
    path_pattern               = "/media/*"
    target_origin_id           = "media"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = false # already WebP
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
  }

  dynamic "ordered_cache_behavior" {
    for_each = local.app_paths

    content {
      path_pattern               = ordered_cache_behavior.value
      target_origin_id           = "app"
      viewer_protocol_policy     = "redirect-to-https"
      allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods             = ["GET", "HEAD"]
      compress                   = true
      cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
      origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
      response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.acm_certificate_arn == ""
    acm_certificate_arn            = var.acm_certificate_arn == "" ? null : var.acm_certificate_arn
    ssl_support_method             = var.acm_certificate_arn == "" ? null : "sni-only"
    minimum_protocol_version       = var.acm_certificate_arn == "" ? "TLSv1" : "TLSv1.2_2021"
  }

  tags = { Name = local.name }
}
