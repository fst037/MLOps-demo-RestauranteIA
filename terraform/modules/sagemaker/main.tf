# Verifica que el modelo empaquetado existe en S3 antes de crear el endpoint.
# deploy.ps1 sube este archivo en la fase previa al plan completo.
data "aws_s3_object" "model_tar" {
  bucket = var.bucket_name
  key    = "models/bistrotech-model.tar.gz"
}

resource "aws_sagemaker_model" "bistrotech" {
  name               = "bistrotech-recomendador-v1"
  execution_role_arn = var.role_arn

  primary_container {
    image          = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.7-1"
    model_data_url = "s3://${var.bucket_name}/models/bistrotech-model.tar.gz"

    environment = {
      SAGEMAKER_PROGRAM          = "inference.py"
      SAGEMAKER_SUBMIT_DIRECTORY = "/opt/ml/model/code"
    }
  }

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }

  depends_on = [data.aws_s3_object.model_tar]
}

resource "aws_sagemaker_endpoint_configuration" "bistrotech" {
  name = "bistrotech-config-v1"

  production_variants {
    variant_name = "primary"
    model_name   = aws_sagemaker_model.bistrotech.name

    serverless_config {
      memory_size_in_mb = 2048
      max_concurrency   = 5
    }
  }

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_sagemaker_endpoint" "bistrotech" {
  name                 = var.endpoint_name
  endpoint_config_name = aws_sagemaker_endpoint_configuration.bistrotech.name

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_sagemaker_endpoint_configuration.bistrotech]
}
