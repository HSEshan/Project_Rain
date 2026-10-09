# The cost guardrail. Account-wide rather than filtered to this project's tags,
# because a tag filter only works once the Project tag has been activated as a
# cost allocation tag in the Billing console (a manual step that takes up to a
# day) and a budget that silently matches nothing is worse than a broad one.
#
# A budget only *tells* you. It does not stop anything; scripts/stop.sh and
# scripts/teardown.sh do. The first two budgets in an account are free.

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  # Forecast rather than actual at 100%: by the time the actual spend crosses
  # the limit it is too late to do anything about this month.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
