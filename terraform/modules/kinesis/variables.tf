variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "kinesis_shard_count" {
  description = "Number of shards for each stream"
  type        = number
}
