data "archive_file" "trigger" {
  type        = "zip"
  source_file = "${path.module}/lambda_src/trigger.py"
  output_path = "${path.module}/lambda_src/trigger.zip"
}

data "archive_file" "deploy" {
  type        = "zip"
  source_file = "${path.module}/lambda_src/deploy.py"
  output_path = "${path.module}/lambda_src/deploy.zip"
}

data "archive_file" "api_handler" {
  type        = "zip"
  source_file = "${path.module}/lambda_src/api_handler.py"
  output_path = "${path.module}/lambda_src/api_handler.zip"
}

# Lambda 1 — trigger mini-batch, invocada cada 5 minutos por EventBridge
resource "aws_lambda_function" "trigger" {
  filename         = data.archive_file.trigger.output_path
  function_name    = "${var.project_name}-trigger-minibatch"
  role             = var.role_arn
  handler          = "trigger.handler"
  runtime          = "python3.12"
  timeout          = var.lambda_timeout_trigger
  source_code_hash = data.archive_file.trigger.output_base64sha256

  environment {
    variables = {
      RETRAIN_THRESHOLD = tostring(var.retrain_threshold)
      S3_BUCKET         = var.bucket_name
      PIPELINE_NAME     = "${var.project_name}-retrain-pipeline"
      # AWS_REGION la provee el runtime de Lambda automáticamente
    }
  }

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_cloudwatch_event_rule" "trigger_schedule" {
  name                = "${var.project_name}-trigger-schedule"
  description         = "Dispara la Lambda de mini-batch cada 5 minutos"
  schedule_expression = "rate(5 minutes)"

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_cloudwatch_event_target" "trigger_lambda" {
  rule      = aws_cloudwatch_event_rule.trigger_schedule.name
  target_id = "TriggerMinibatchLambda"
  arn       = aws_lambda_function.trigger.arn
}

resource "aws_lambda_permission" "eventbridge_trigger" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.trigger.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.trigger_schedule.arn
}

# Lambda 2 — deploy full-automático, invocada por SageMaker Pipeline
resource "aws_lambda_function" "deploy" {
  filename         = data.archive_file.deploy.output_path
  function_name    = "${var.project_name}-deploy-fullautom"
  role             = var.role_arn
  handler          = "deploy.handler"
  runtime          = "python3.12"
  timeout          = var.lambda_timeout_deploy
  source_code_hash = data.archive_file.deploy.output_base64sha256

  environment {
    variables = {
      ENDPOINT_NAME         = var.endpoint_name
      IMPROVEMENT_THRESHOLD = tostring(var.improvement_threshold)
      S3_BUCKET             = var.bucket_name
      # AWS_REGION la provee el runtime de Lambda automáticamente
    }
  }

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_lambda_permission" "sagemaker_deploy" {
  statement_id  = "AllowSageMakerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.deploy.function_name
  principal     = "sagemaker.amazonaws.com"
}

# Lambda 3 — handler de API Gateway → SageMaker Endpoint
resource "aws_lambda_function" "api_handler" {
  filename         = data.archive_file.api_handler.output_path
  function_name    = "${var.project_name}-api-handler"
  role             = var.role_arn
  handler          = "api_handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  source_code_hash = data.archive_file.api_handler.output_base64sha256

  environment {
    variables = {
      ENDPOINT_NAME = var.endpoint_name
      # AWS_REGION la provee el runtime de Lambda automáticamente
    }
  }

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}
