output "api_handler_arn" {
  description = "ARN of the API handler Lambda"
  value       = aws_lambda_function.api_handler.arn
}

output "api_handler_name" {
  description = "Name of the API handler Lambda"
  value       = aws_lambda_function.api_handler.function_name
}

output "trigger_lambda_arn" {
  description = "ARN of the trigger mini-batch Lambda"
  value       = aws_lambda_function.trigger.arn
}

output "deploy_lambda_arn" {
  description = "ARN of the deploy full-auto Lambda"
  value       = aws_lambda_function.deploy.arn
}
