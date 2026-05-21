variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "endpoint_name" {
  description = "SageMaker endpoint name"
  type        = string
}

variable "retrain_threshold" {
  description = "Number of complete records to trigger retraining"
  type        = number
}

variable "improvement_threshold" {
  description = "Minimum improvement fraction for auto-deploy"
  type        = number
}

variable "bucket_name" {
  description = "S3 bucket name"
  type        = string
}

variable "role_arn" {
  description = "IAM role ARN for Lambda execution"
  type        = string
}

variable "lambda_timeout_trigger" {
  description = "Timeout in seconds for trigger Lambda"
  type        = number
}

variable "lambda_timeout_deploy" {
  description = "Timeout in seconds for deploy Lambda"
  type        = number
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}
