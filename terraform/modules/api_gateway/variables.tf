variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "api_handler_arn" {
  description = "ARN of the API handler Lambda"
  type        = string
}

variable "api_handler_name" {
  description = "Name of the API handler Lambda"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}
