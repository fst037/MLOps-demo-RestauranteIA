output "dashboard_url" {
  description = "URL of the BistroTech MLOps CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.bistrotech.dashboard_name}"
}

output "drift_alarm_arn" {
  description = "ARN of the model drift severity alarm"
  value       = aws_cloudwatch_metric_alarm.model_drift_severe.arn
}

output "endpoint_errors_alarm_arn" {
  description = "ARN of the endpoint errors alarm"
  value       = aws_cloudwatch_metric_alarm.endpoint_errors.arn
}
