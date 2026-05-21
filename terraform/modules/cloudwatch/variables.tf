variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "endpoint_name" {
  description = "SageMaker endpoint name (used for dimensions in alarms)"
  type        = string
}

variable "aws_region" {
  description = "AWS region (used for dashboard URL)"
  type        = string
}
