resource "aws_cloudwatch_metric_alarm" "model_drift_severe" {
  alarm_name          = "BistroTech-ModelDrift-Severe"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "propina_rate_psi"
  namespace           = "BistroTech/ModelDrift"
  period              = 3600
  statistic           = "Average"
  threshold           = 0.20
  alarm_description   = "PSI del propina_rate supera 0.20 — drift severo detectado. Revisar reentrenamiento."
  treat_missing_data  = "notBreaching"

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_cloudwatch_metric_alarm" "endpoint_errors" {
  alarm_name          = "BistroTech-EndpointErrors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Invocation5XXErrors"
  namespace           = "AWS/SageMaker"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "SageMaker endpoint reporta >= 5 errores 5XX en 5 minutos"
  treat_missing_data  = "notBreaching"

  dimensions = {
    EndpointName = var.endpoint_name
    VariantName  = "primary"
  }

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_cloudwatch_dashboard" "bistrotech" {
  dashboard_name = "BistroTech-MLOps"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "alarm"
        x      = 0
        y      = 0
        width  = 24
        height = 4
        properties = {
          alarms = [
            aws_cloudwatch_metric_alarm.model_drift_severe.arn,
            aws_cloudwatch_metric_alarm.endpoint_errors.arn,
          ]
          title = "Estado de Alarmas BistroTech"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 4
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["BistroTech/ModelDrift", "propina_rate_psi"]
          ]
          view   = "timeSeries"
          region = var.aws_region
          period = 3600
          title  = "Model Drift — PSI propina_rate"
          annotations = {
            horizontal = [
              { value = 0.20, label = "Umbral drift severo", color = "#ff0000" }
            ]
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 4
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/SageMaker", "Invocation5XXErrors",
              "EndpointName", var.endpoint_name,
              "VariantName", "primary"]
          ]
          view   = "timeSeries"
          region = var.aws_region
          period = 300
          title  = "Endpoint 5XX Errors"
          annotations = {
            horizontal = [
              { value = 5, label = "Umbral de alerta", color = "#ff0000" }
            ]
          }
        }
      }
    ]
  })
}
