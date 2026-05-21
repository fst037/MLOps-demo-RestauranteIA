resource "aws_iam_role" "sagemaker_bistrotech" {
  name = "SageMakerBistroTechRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = [
            "sagemaker.amazonaws.com",
            "lambda.amazonaws.com"
          ]
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = "bistrotech"
    Environment = "academic"
  }
}

resource "aws_iam_role_policy_attachment" "sagemaker_full" {
  role       = aws_iam_role.sagemaker_bistrotech.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_iam_role_policy_attachment" "s3_full" {
  role       = aws_iam_role.sagemaker_bistrotech.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "kinesis_full" {
  role       = aws_iam_role.sagemaker_bistrotech.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonKinesisFullAccess"
}

resource "aws_iam_role_policy_attachment" "cloudwatch_full" {
  role       = aws_iam_role.sagemaker_bistrotech.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchFullAccess"
}

resource "aws_iam_role_policy_attachment" "lambda_full" {
  role       = aws_iam_role.sagemaker_bistrotech.name
  policy_arn = "arn:aws:iam::aws:policy/AWSLambda_FullAccess"
}
