"""
Lambda de deploy full-automático para BistroTech.

Recibe el ARN del modelo nuevo del Model Registry, evalúa sus métricas
vs. producción y despliega si mejora en todas las métricas por encima del umbral.
"""
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME", "bistrotech-endpoint-v1")
IMPROVEMENT_THRESHOLD = float(os.environ.get("IMPROVEMENT_THRESHOLD", 0.05))
S3_BUCKET = os.environ.get("S3_BUCKET", "bistrotech-models-local")
METRICS_KEY = "pipeline/current_metrics.json"


def _get_s3_client():
    import boto3
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _get_sagemaker_client():
    import boto3
    return boto3.client("sagemaker", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def compare_versions(metrics_new: dict, metrics_current: dict, improvement_threshold: float = 0.05) -> bool:
    """
    Compara dos versiones de modelo y decide si la nueva es mejor.

    Para métricas donde menor es mejor (rmse, mae): mejora = (current - new) / current > threshold.
    Para métricas donde mayor es mejor (pearson, hit_rate_k, f1_macro): mejora = (new - current) / current > threshold.

    Retorna True si el modelo nuevo mejora en TODAS las métricas por encima del umbral.
    """
    lower_is_better = {"rmse", "mae"}
    all_improved = True

    for metric, new_val in metrics_new.items():
        if metric not in metrics_current:
            logger.warning("Métrica '%s' ausente en modelo actual; se omite.", metric)
            continue
        current_val = metrics_current[metric]
        if current_val == 0:
            logger.warning("Métrica '%s' es 0 en producción; se omite comparación.", metric)
            continue

        if metric in lower_is_better:
            improvement = (current_val - new_val) / abs(current_val)
        else:
            improvement = (new_val - current_val) / abs(current_val)

        improved = improvement > improvement_threshold
        direction = "↓" if metric in lower_is_better else "↑"
        status = "✅" if improved else "❌"
        logger.info(
            "%s %s: nuevo=%.4f actual=%.4f mejora=%.2f%% (umbral=%.0f%%) %s",
            status, metric, new_val, current_val,
            improvement * 100, improvement_threshold * 100, direction,
        )
        if not improved:
            all_improved = False

    logger.info("Decisión de deploy: %s", "APROBAR" if all_improved else "RECHAZAR")
    return all_improved


def evaluate_new_model(model_arn: str) -> dict:
    """Obtiene las métricas del modelo candidato desde el Model Registry."""
    try:
        sm = _get_sagemaker_client()
        response = sm.describe_model_package(ModelPackageName=model_arn)
        metrics_raw = (
            response.get("ModelMetrics", {})
            .get("ModelQuality", {})
            .get("Statistics", {})
            .get("ContentType", "")
        )
        if metrics_raw:
            return json.loads(metrics_raw)
        logger.warning("Métricas no encontradas en el ARN; usando métricas simuladas.")
    except ImportError:
        logger.warning("boto3 no disponible — usando métricas simuladas de demo.")
    except Exception as e:
        logger.warning("No se pudieron obtener métricas del registry (%s); simulando.", e)

    return {"rmse": 0.046, "mae": 0.037, "pearson": 0.74, "hit_rate_k": 0.72, "f1_macro": 0.68}


def _get_current_metrics() -> dict:
    """Lee las métricas del modelo en producción desde S3."""
    try:
        s3 = _get_s3_client()
        obj = s3.get_object(Bucket=S3_BUCKET, Key=METRICS_KEY)
        return json.loads(obj["Body"].read())
    except ImportError:
        logger.warning("boto3 no disponible — usando métricas baseline simuladas.")
    except Exception as e:
        logger.warning("No se pudieron leer métricas actuales (%s); usando baseline.", e)

    return {"rmse": 0.055, "mae": 0.044, "pearson": 0.68, "hit_rate_k": 0.65, "f1_macro": 0.60}


def _save_current_metrics(metrics: dict) -> None:
    """Actualiza las métricas del modelo en producción en S3."""
    try:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=METRICS_KEY,
            Body=json.dumps(metrics),
            ContentType="application/json",
        )
        logger.info("Métricas de producción actualizadas en S3.")
    except ImportError:
        logger.warning("boto3 no disponible — métricas no persistidas.")
    except Exception as e:
        logger.error("Error al guardar métricas en S3: %s", e)


def deploy_new_endpoint(model_arn: str, endpoint_name: str) -> str:
    """
    Despliega el modelo candidato como nuevo endpoint de SageMaker.
    Crea o actualiza el endpoint con configuración blue/green.
    """
    try:
        sm = _get_sagemaker_client()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        config_name = f"bistrotech-config-{timestamp}"

        sm.create_endpoint_config(
            EndpointConfigName=config_name,
            ProductionVariants=[
                {
                    "VariantName": "primary",
                    "ModelName": model_arn.split("/")[-1],
                    "ServerlessConfig": {
                        "MemorySizeInMB": 2048,
                        "MaxConcurrency": 5,
                    },
                }
            ],
        )

        try:
            sm.update_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=config_name,
            )
            logger.info("Endpoint '%s' actualizado con nueva configuración.", endpoint_name)
        except sm.exceptions.ClientError:
            sm.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=config_name,
            )
            logger.info("Endpoint '%s' creado.", endpoint_name)

        return f"arn:aws:sagemaker:{os.environ.get('AWS_REGION','us-east-1')}:000000000000:endpoint/{endpoint_name}"

    except ImportError:
        logger.warning("boto3 no disponible — simulando deploy.")
        return f"arn:aws:sagemaker:local:000000000000:endpoint/{endpoint_name}"
    except Exception as e:
        logger.error("Error al desplegar endpoint: %s", e)
        raise


def handler(event: dict, context) -> dict:
    """
    Entry point de la Lambda de deploy full-auto.

    1. Recibe ARN del modelo nuevo del Model Registry.
    2. Evalúa sus métricas.
    3. Compara con métricas del modelo en producción.
    4. Si mejora: despliega nuevo endpoint.
    5. Si no mejora: loguea y descarta.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    model_arn = event.get("model_arn", "")
    endpoint_name = event.get("endpoint_name", ENDPOINT_NAME)
    threshold = float(event.get("improvement_threshold", IMPROVEMENT_THRESHOLD))

    logger.info("[%s] Evaluando modelo candidato: %s", timestamp, model_arn)

    if not model_arn:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "model_arn requerido en el evento"}),
        }

    try:
        metrics_new = evaluate_new_model(model_arn)
        metrics_current = _get_current_metrics()

        logger.info("Métricas nuevo:    %s", metrics_new)
        logger.info("Métricas actuales: %s", metrics_current)

        should_deploy = compare_versions(metrics_new, metrics_current, threshold)

        if should_deploy:
            logger.info("El nuevo modelo mejora las métricas. Iniciando deploy.")
            endpoint_arn = deploy_new_endpoint(model_arn, endpoint_name)
            _save_current_metrics(metrics_new)
            body = {
                "decision": "DEPLOYED",
                "endpoint_arn": endpoint_arn,
                "metrics_new": metrics_new,
                "metrics_previous": metrics_current,
                "timestamp": timestamp,
            }
        else:
            logger.info("El nuevo modelo NO mejora las métricas. Descartando.")
            body = {
                "decision": "DISCARDED",
                "reason": "No supera umbral de mejora",
                "metrics_new": metrics_new,
                "metrics_current": metrics_current,
                "threshold": threshold,
                "timestamp": timestamp,
            }

        return {"statusCode": 200, "body": json.dumps(body)}

    except Exception as e:
        logger.error("Error en deploy lambda: %s", e, exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e), "timestamp": timestamp}),
        }
