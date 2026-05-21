resource "aws_s3_bucket" "models" {
  bucket = "${var.project_name}-models-${var.account_id}"

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_s3_bucket_public_access_block" "models" {
  bucket = aws_s3_bucket.models.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "last_train_counter" {
  bucket       = aws_s3_bucket.models.id
  key          = "pipeline/last_train_counter.json"
  content      = jsonencode({ new_complete_records = 0 })
  content_type = "application/json"
}

resource "aws_s3_object" "current_metrics" {
  bucket       = aws_s3_bucket.models.id
  key          = "pipeline/current_metrics.json"
  content = jsonencode({
    rmse       = 0.055
    mae        = 0.044
    pearson    = 0.68
    hit_rate_k = 0.65
    f1_macro   = 0.60
  })
  content_type = "application/json"
}
