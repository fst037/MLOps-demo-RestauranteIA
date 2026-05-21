resource "aws_kinesis_stream" "eventos" {
  name             = "${var.project_name}-eventos"
  shard_count      = var.kinesis_shard_count
  retention_period = 24

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_kinesis_stream" "feedback" {
  name             = "${var.project_name}-feedback"
  shard_count      = var.kinesis_shard_count
  retention_period = 24

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}
