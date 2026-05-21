"""
Deploy inicial del endpoint SageMaker para BistroTech.

Requiere SAGEMAKER_ROLE_ARN y S3_BUCKET configurados como variables de entorno.
"""
import logging
import os

logger = logging.getLogger(__name__)

SAGEMAKER_ROLE = os.environ.get("SAGEMAKER_ROLE_ARN", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "bistrotech-models")
ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME", "bistrotech-endpoint-v1")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
INSTANCE_TYPE = "ml.m5.large"


def deploy_endpoint(model_s3_uri: str, endpoint_name: str = ENDPOINT_NAME) -> str:
    """
    Despliega el modelo empaquetado en S3 como un SageMaker Endpoint.

    Args:
        model_s3_uri: URI S3 del modelo .tar.gz (ej: s3://bucket/models/model.tar.gz).
        endpoint_name: nombre del endpoint a crear/actualizar.

    Returns:
        URL del endpoint creado.
    """
    try:
        import sagemaker
        from sagemaker.model import Model

        sess = sagemaker.Session()
        role = SAGEMAKER_ROLE or sagemaker.get_execution_role()

        model = Model(
            image_uri=f"763104351884.dkr.ecr.{AWS_REGION}.amazonaws.com/xgboost:1.7-1",
            model_data=model_s3_uri,
            role=role,
            entry_point="serve/inference.py",
            source_dir=".",
            sagemaker_session=sess,
        )

        predictor = model.deploy(
            initial_instance_count=1,
            instance_type=INSTANCE_TYPE,
            endpoint_name=endpoint_name,
        )

        endpoint_url = f"https://runtime.sagemaker.{AWS_REGION}.amazonaws.com/endpoints/{endpoint_name}/invocations"
        logger.info("Endpoint desplegado: %s", endpoint_url)
        return endpoint_url

    except ImportError:
        logger.error("sagemaker SDK no instalado.")
        raise
    except Exception as e:
        logger.error("Error al desplegar: %s", e)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not SAGEMAKER_ROLE:
        print("SAGEMAKER_ROLE_ARN no configurado. Ejemplo de uso:")
        print("  export SAGEMAKER_ROLE_ARN=arn:aws:iam::123456789:role/SageMakerRole")
        print("  export S3_BUCKET=bistrotech-models-123456789")
        print("  python infrastructure/deploy_sagemaker.py")
    else:
        model_uri = f"s3://{S3_BUCKET}/models/model.tar.gz"
        url = deploy_endpoint(model_uri)
        print(f"Endpoint URL: {url}")
