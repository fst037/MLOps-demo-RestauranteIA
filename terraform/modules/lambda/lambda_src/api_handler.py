import boto3
import json
import os


def handler(event, context):
    runtime = boto3.client("sagemaker-runtime",
                           region_name=os.environ["AWS_REGION"])
    response = runtime.invoke_endpoint(
        EndpointName=os.environ["ENDPOINT_NAME"],
        ContentType="application/json",
        Body=event["body"],
    )
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": response["Body"].read().decode(),
    }
