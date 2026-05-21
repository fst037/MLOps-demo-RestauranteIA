output "account_id" {
  description = "AWS Account ID used in this deploy"
  value       = local.account_id
}

output "s3_bucket_name" {
  description = "S3 bucket name for models and pipeline data"
  value       = module.s3.bucket_name
}

output "endpoint_name" {
  description = "SageMaker endpoint name"
  value       = module.sagemaker.endpoint_name
}

output "api_url" {
  description = "Full URL of the API Gateway predict endpoint"
  value       = module.api_gateway.api_url
}

output "dashboard_url" {
  description = "CloudWatch MLOps dashboard URL"
  value       = module.cloudwatch.dashboard_url
}

output "deploy_message" {
  description = "Deploy success message"
  value       = "✅ BistroTech deployado. Endpoint listo en: ${module.api_gateway.api_url}"
}
