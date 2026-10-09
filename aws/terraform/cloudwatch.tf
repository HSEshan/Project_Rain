# Logs off the box, one metric derived from them, and alarms that actually
# reach a person. tasks.md Phase 21: "logs off the box and one alarm that
# actually fires". scripts/test-alarm.sh fires it for real, end to end.
#
# Every container logs straight to this group through Docker's awslogs driver
# (aws/docker-compose.aws.yml), one stream per container. No agent to install
# or keep running, and nothing is written to the instance's disk, which is the
# log-rotation problem the VPS still has (Phase 6).

resource "aws_cloudwatch_log_group" "app" {
  name              = "/${var.project}/${var.environment}"
  retention_in_days = var.log_retention_days
}

# The services log JSON in production (LOG_FORMAT=json), and structlog writes
# the level as `"level": "error"`. A JSON metric filter reads that field
# directly; lines that are not JSON (uvicorn's access log, LiveKit's startup
# banner) simply do not match.
resource "aws_cloudwatch_log_metric_filter" "errors" {
  name           = "${local.name}-errors"
  log_group_name = aws_cloudwatch_log_group.app.name
  pattern        = "{ ($.level = \"error\") || ($.level = \"critical\") }"

  metric_transformation {
    name          = "ErrorLogLines"
    namespace     = "ProjectRain/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

# AWS mails a confirmation link first. Until it is clicked, alarms fire into a
# topic with no confirmed subscriber and nobody hears about it.
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# --- the one that fires ------------------------------------------------------
# Any error logged by any service. One line is enough: this deployment has no
# traffic to speak of, so an error is news rather than noise.
resource "aws_cloudwatch_metric_alarm" "app_errors" {
  alarm_name          = "${local.name}-app-errors"
  alarm_description   = "A service logged an error. Read it with scripts/logs.sh."
  namespace           = "ProjectRain/${var.environment}"
  metric_name         = "ErrorLogLines"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

# --- the instance itself -----------------------------------------------------
# A failed *system* check is AWS's hardware or network under the instance. The
# recover action moves it to healthy hardware, keeping its id, address, disk
# and data. Nothing else in this stack would notice or fix that.
resource "aws_cloudwatch_metric_alarm" "instance_recover" {
  alarm_name          = "${local.name}-instance-system-check"
  alarm_description   = "Underlying host failed; EC2 is recovering the instance onto new hardware."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed_System"
  dimensions          = { InstanceId = aws_instance.app.id }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions = [
    "arn:aws:automate:${var.region}:ec2:recover",
    aws_sns_topic.alerts.arn,
  ]
}

# The instance's own check failing (a hung kernel, a full disk) is not
# something recovery fixes, so this one only tells a person.
resource "aws_cloudwatch_metric_alarm" "instance_check" {
  alarm_name          = "${local.name}-instance-check"
  alarm_description   = "The instance failed its own status check. Try scripts/stop.sh then start.sh."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed_Instance"
  dimensions          = { InstanceId = aws_instance.app.id }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# With cpu_credits = "standard" (ec2.tf), running out of credits throttles the
# instance to its baseline, 20% of a vCPU on a t4g.small. Everything gets slow
# for no visible reason; this is the visible reason.
resource "aws_cloudwatch_metric_alarm" "cpu_credits" {
  alarm_name          = "${local.name}-cpu-credits-low"
  alarm_description   = "CPU credits nearly gone; the instance will be throttled to baseline."
  namespace           = "AWS/EC2"
  metric_name         = "CPUCreditBalance"
  dimensions          = { InstanceId = aws_instance.app.id }
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 20
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# --- one screen ---------------------------------------------------------------
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = local.name

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title   = "Errors logged"
          region  = var.region
          stat    = "Sum"
          period  = 300
          metrics = [["ProjectRain/${var.environment}", "ErrorLogLines"]]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title  = "Instance CPU and credits"
          region = var.region
          period = 300
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.app.id],
            ["AWS/EC2", "CPUCreditBalance", "InstanceId", aws_instance.app.id, { yAxis = "right" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title  = "Instance network (includes all voice media)"
          region = var.region
          stat   = "Sum"
          period = 300
          metrics = [
            ["AWS/EC2", "NetworkIn", "InstanceId", aws_instance.app.id],
            ["AWS/EC2", "NetworkOut", "InstanceId", aws_instance.app.id],
          ]
        }
      },
      {
        # CloudFront metrics are global and published in us-east-1 only
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title  = "CloudFront requests and error rate"
          region = "us-east-1"
          period = 300
          metrics = [
            ["AWS/CloudFront", "Requests", "DistributionId", aws_cloudfront_distribution.main.id, "Region", "Global", { stat = "Sum" }],
            ["AWS/CloudFront", "5xxErrorRate", "DistributionId", aws_cloudfront_distribution.main.id, "Region", "Global", { stat = "Average", yAxis = "right" }],
          ]
        }
      },
      {
        type = "log", x = 0, y = 12, width = 24, height = 6
        properties = {
          title  = "Recent errors"
          region = var.region
          query  = "SOURCE '${aws_cloudwatch_log_group.app.name}' | fields @timestamp, @logStream, @message | filter level = 'error' or level = 'critical' | sort @timestamp desc | limit 50"
          view   = "table"
        }
      },
    ]
  })
}
