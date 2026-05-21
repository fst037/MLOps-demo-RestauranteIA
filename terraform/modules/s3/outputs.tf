output "bucket_name" {
  description = "Name of the S3 bucket for models and pipeline data"
  value       = aws_s3_bucket.models.id
}

output "bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.models.arn
}
