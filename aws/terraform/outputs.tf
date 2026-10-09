# Read by the scripts in aws/scripts through `terraform output -raw <name>`,
# so a rename here is a rename there.

output "app_url" {
  description = "Where the app is."
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "cloudfront_domain" {
  description = "Point a custom domain's CNAME here."
  value       = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "region" {
  value = var.region
}

output "name" {
  description = "Prefix of every resource name, e.g. project-rain-poc."
  value       = local.name
}

output "project_tag" {
  value = var.project
}

output "instance_id" {
  value = aws_instance.app.id
}

output "instance_public_ip" {
  description = "LiveKit advertises this for voice media. The web app is only reachable through CloudFront."
  value       = aws_eip.app.public_ip
}

output "media_bucket" {
  value = aws_s3_bucket.this["media"].bucket
}

output "frontend_bucket" {
  value = aws_s3_bucket.this["frontend"].bucket
}

output "artifacts_bucket" {
  value = aws_s3_bucket.this["artifacts"].bucket
}

output "log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "ssm_prefix" {
  value = local.ssm_prefix
}

output "db_endpoint" {
  description = "Empty unless use_rds is true."
  value       = var.use_rds ? aws_db_instance.main[0].address : ""
}

output "use_rds" {
  value = var.use_rds
}

output "dashboard_url" {
  value = "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards/dashboard/${aws_cloudwatch_dashboard.main.dashboard_name}"
}
