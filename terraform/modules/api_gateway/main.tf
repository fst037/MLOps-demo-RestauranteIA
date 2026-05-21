resource "aws_api_gateway_rest_api" "bistrotech" {
  name = "${var.project_name}-api"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_api_gateway_resource" "predict" {
  rest_api_id = aws_api_gateway_rest_api.bistrotech.id
  parent_id   = aws_api_gateway_rest_api.bistrotech.root_resource_id
  path_part   = "predict"
}

resource "aws_api_gateway_method" "predict_post" {
  rest_api_id   = aws_api_gateway_rest_api.bistrotech.id
  resource_id   = aws_api_gateway_resource.predict.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "predict_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.bistrotech.id
  resource_id             = aws_api_gateway_resource.predict.id
  http_method             = aws_api_gateway_method.predict_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${var.api_handler_arn}/invocations"
}

resource "aws_api_gateway_deployment" "bistrotech" {
  rest_api_id = aws_api_gateway_rest_api.bistrotech.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.predict.id,
      aws_api_gateway_method.predict_post.id,
      aws_api_gateway_integration.predict_lambda.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration.predict_lambda]
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.bistrotech.id
  rest_api_id   = aws_api_gateway_rest_api.bistrotech.id
  stage_name    = "prod"

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.api_handler_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.bistrotech.execution_arn}/*/*"
}
