variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "bistrotech"
}

variable "endpoint_name" {
  description = "SageMaker endpoint name"
  type        = string
  default     = "bistrotech-endpoint-v1"
}

variable "retrain_threshold" {
  description = "Number of complete records to trigger retraining"
  type        = number
  default     = 50
}

variable "improvement_threshold" {
  description = "Minimum improvement ratio to auto-deploy new model (e.g. 0.05 = 5%)"
  type        = number
  default     = 0.05
}

variable "sagemaker_instance_type" {
  description = "SageMaker endpoint instance type"
  type        = string
  default     = "ml.m5.large"
}

variable "lambda_timeout_trigger" {
  description = "Timeout in seconds for the trigger Lambda"
  type        = number
  default     = 60
}

variable "lambda_timeout_deploy" {
  description = "Timeout in seconds for the deploy Lambda"
  type        = number
  default     = 120
}

variable "kinesis_shard_count" {
  description = "Number of shards for each Kinesis stream"
  type        = number
  default     = 1
}
