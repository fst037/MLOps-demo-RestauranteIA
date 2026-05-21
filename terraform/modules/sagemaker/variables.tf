variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "endpoint_name" {
  description = "SageMaker endpoint name"
  type        = string
}

variable "role_arn" {
  description = "IAM role ARN for SageMaker execution"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket name containing model artifacts"
  type        = string
}
