output "api_url" {
  description = "Full invoke URL of the /predict endpoint"
  value       = "${aws_api_gateway_stage.prod.invoke_url}/predict"
}

output "api_id" {
  description = "ID of the API Gateway REST API"
  value       = aws_api_gateway_rest_api.bistrotech.id
}
