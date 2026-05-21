output "stream_eventos_arn" {
  description = "ARN of the bistrotech-eventos Kinesis stream"
  value       = aws_kinesis_stream.eventos.arn
}

output "stream_feedback_arn" {
  description = "ARN of the bistrotech-feedback Kinesis stream"
  value       = aws_kinesis_stream.feedback.arn
}

output "stream_eventos_name" {
  description = "Name of the eventos Kinesis stream"
  value       = aws_kinesis_stream.eventos.name
}

output "stream_feedback_name" {
  description = "Name of the feedback Kinesis stream"
  value       = aws_kinesis_stream.feedback.name
}
