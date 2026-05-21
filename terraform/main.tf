terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "bistrotech"
      Environment = "academic"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

module "iam" {
  source = "./modules/iam"
}

module "s3" {
  source       = "./modules/s3"
  account_id   = local.account_id
  project_name = var.project_name
  depends_on   = [module.iam]
}

# module "kinesis" disabled — AWS Educate accounts lack Kinesis subscription;
# streams are unused by all other modules so this is safe to skip.
# module "kinesis" {
#   source              = "./modules/kinesis"
#   project_name        = var.project_name
#   kinesis_shard_count = var.kinesis_shard_count
# }

module "sagemaker" {
  source       = "./modules/sagemaker"
  project_name = var.project_name
  endpoint_name = var.endpoint_name
  role_arn     = module.iam.role_arn
  bucket_name  = module.s3.bucket_name
  depends_on   = [module.iam, module.s3]
}

module "lambda" {
  source                 = "./modules/lambda"
  project_name           = var.project_name
  endpoint_name          = var.endpoint_name
  retrain_threshold      = var.retrain_threshold
  improvement_threshold  = var.improvement_threshold
  bucket_name            = module.s3.bucket_name
  role_arn               = module.iam.role_arn
  lambda_timeout_trigger = var.lambda_timeout_trigger
  lambda_timeout_deploy  = var.lambda_timeout_deploy
  aws_region             = var.aws_region
  depends_on             = [module.iam, module.s3, module.sagemaker]
}

module "api_gateway" {
  source           = "./modules/api_gateway"
  project_name     = var.project_name
  api_handler_arn  = module.lambda.api_handler_arn
  api_handler_name = module.lambda.api_handler_name
  aws_region       = var.aws_region
  account_id       = local.account_id
  depends_on       = [module.lambda]
}

module "cloudwatch" {
  source        = "./modules/cloudwatch"
  project_name  = var.project_name
  endpoint_name = var.endpoint_name
  aws_region    = var.aws_region
  depends_on    = [module.sagemaker]
}
