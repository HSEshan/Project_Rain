variable "project" {
  description = "Name prefix and Project tag for every resource."
  type        = string
  default     = "project-rain"
}

variable "environment" {
  description = "Second name component and Environment tag. One stack per value."
  type        = string
  default     = "poc"
}

variable "region" {
  description = "Everything lives in one region. us-east-1 is where CloudFront certificates and metrics live, which saves a second provider."
  type        = string
  default     = "us-east-1"
}

variable "alert_email" {
  description = "Receives CloudWatch alarms and budget warnings. AWS sends a confirmation mail first; nothing arrives until it is clicked."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Account-wide monthly budget. Mails at 50% actual and 100% forecast."
  type        = number
  default     = 20
}

variable "instance_type" {
  description = "t4g.small (2 vCPU, 2 GB, arm64) runs the whole stack. Must match var.architecture."
  type        = string
  default     = "t4g.small"
}

variable "architecture" {
  description = "arm64 for t4g/m7g/c7g, x86_64 for t3/m7i. Every image in the stack is published for both."
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["arm64", "x86_64"], var.architecture)
    error_message = "architecture must be arm64 or x86_64."
  }
}

variable "root_volume_gb" {
  description = "Root EBS volume. Holds Docker images, build cache and (without RDS) the Postgres volume."
  type        = number
  default     = 30
}

variable "use_rds" {
  description = "Run Postgres on RDS instead of a container on the instance. The thing worth learning, and the largest line on the bill."
  type        = bool
  default     = false
}

variable "rds_instance_class" {
  description = "Only used when use_rds is true."
  type        = string
  default     = "db.t4g.micro"
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention. Short on purpose: logs are the one cost that grows while nobody is looking."
  type        = number
  default     = 7
}

variable "cloudfront_price_class" {
  description = "PriceClass_100 serves from North America and Europe only, the cheapest class."
  type        = string
  default     = "PriceClass_100"
}

variable "domain_name" {
  description = "Optional custom hostname, e.g. rain.example.com. Leave empty to use the *.cloudfront.net address."
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "Required with domain_name: an issued ACM certificate for it, in us-east-1 (CloudFront only reads certificates from there)."
  type        = string
  default     = ""

  validation {
    condition     = var.acm_certificate_arn == "" || startswith(var.acm_certificate_arn, "arn:aws:acm:us-east-1:")
    error_message = "CloudFront certificates must be in us-east-1."
  }
}

variable "compose_version" {
  description = "Docker Compose plugin installed on the instance. Needs >= 2.24.4 for the !override tags in aws/docker-compose.aws.yml."
  type        = string
  default     = "2.29.7"
}

variable "buildx_version" {
  description = "Docker Buildx plugin installed on the instance; compose build needs it."
  type        = string
  default     = "0.17.1"
}
