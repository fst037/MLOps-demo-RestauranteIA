output "role_arn" {
  description = "ARN of the SageMakerBistroTechRole IAM role"
  value       = aws_iam_role.sagemaker_bistrotech.arn
}
