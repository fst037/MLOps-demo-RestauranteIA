"""
Lambda de trigger mini-batch para BistroTech.

Consulta cuántos registros completos (con feedback) llegaron desde el último
entrenamiento. Si >= RETRAIN_THRESHOLD, dispara el SageMaker Pipeline.
"""
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

RETRAIN_THRESHOLD = int(os.environ.get("RETRAIN_THRESHOLD", 50))
S3_BUCKET = os.environ.get("S3_BUCKET", "bistrotech-models-local")
COUNTER_KEY = "pipeline/last_train_counter.json"
PIPELINE_NAME = os.environ.get("PIPELINE_NAME", "bistrotech-retrain-pipeline")


def check_complete_records(bucket: str, prefix: str) -> int:
    """
    Cuenta registros donde propina_rate no es null en el Feature Store / S3.

    Simula la consulta al Feature Store leyendo un JSON de contador desde S3.
    En producción reemplazar por una query Athena o Feature Store API.
    """
    try:
        import boto3
        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        obj = s3.get_object(Bucket=bucket, Key=prefix)
        data = json.loads(obj["Body"].read())
        count = int(data.get("new_complete_records", 0))
        logger.info("Registros completos desde último entrenamiento: %d", count)
        return count
    except ImportError:
        logger.warning("boto3 no disponible — simulando 0 registros.")
        return 0
    except Exception as e:
        logger.warning("No se pudo leer contador de S3 (%s); usando 0.", e)
        return 0


def trigger_pipeline(pipeline_name: str) -> str:
    """Dispara una ejecución del SageMaker Pipeline."""
    try:
        import boto3
        sm = boto3.client("sagemaker", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        response = sm.start_pipeline_execution(
            PipelineName=pipeline_name,
            PipelineExecutionDisplayName=f"retrain-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        )
        arn = response["PipelineExecutionArn"]
        logger.info("Pipeline disparado: %s", arn)
        return arn
    except ImportError:
        logger.warning("boto3 no disponible — simulando trigger de pipeline.")
        return f"arn:aws:sagemaker:local:000000000000:pipeline/{pipeline_name}/execution/simulated"
    except Exception as e:
        logger.error("Error al disparar pipeline: %s", e)
        raise


def _update_counter(bucket: str, prefix: str, count_used: int) -> None:
    """Resetea el contador en S3 restando los registros procesados."""
    try:
        import boto3
        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        try:
            obj = s3.get_object(Bucket=bucket, Key=prefix)
            data = json.loads(obj["Body"].read())
        except Exception:
            data = {}

        current = int(data.get("new_complete_records", 0))
        data["new_complete_records"] = max(0, current - count_used)
        data["last_updated"] = datetime.now(timezone.utc).isoformat()

        s3.put_object(
            Bucket=bucket,
            Key=prefix,
            Body=json.dumps(data),
            ContentType="application/json",
        )
        logger.info("Contador actualizado en S3: %d registros restantes.", data["new_complete_records"])
    except ImportError:
        logger.warning("boto3 no disponible — contador no actualizado.")
    except Exception as e:
        logger.error("Error al actualizar contador en S3: %s", e)


def handler(event: dict, context) -> dict:
    """
    Entry point de la Lambda de trigger mini-batch.

    1. Consulta cuántos registros completos llegaron desde el último retrain.
    2. Si >= RETRAIN_THRESHOLD: dispara SageMaker Pipeline.
    3. Actualiza el contador en S3.
    4. Loguea la decisión con timestamp.
    """
    threshold = int(event.get("retrain_threshold", RETRAIN_THRESHOLD))
    bucket = event.get("s3_bucket", S3_BUCKET)
    prefix = event.get("counter_key", COUNTER_KEY)
    pipeline_name = event.get("pipeline_name", PIPELINE_NAME)

    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info("[%s] Iniciando verificación de trigger mini-batch.", timestamp)

    if "new_complete_records" in event:
        new_records = int(event["new_complete_records"])
        logger.info("Override local: new_complete_records=%d (del evento).", new_records)
    else:
        new_records = check_complete_records(bucket, prefix)
    logger.info("Registros completos nuevos: %d (threshold: %d)", new_records, threshold)

    if new_records >= threshold:
        logger.info("Threshold alcanzado. Disparando pipeline '%s'.", pipeline_name)
        try:
            execution_arn = trigger_pipeline(pipeline_name)
            _update_counter(bucket, prefix, new_records)
            body = {
                "decision": "RETRAIN_TRIGGERED",
                "new_records": new_records,
                "threshold": threshold,
                "execution_arn": execution_arn,
                "timestamp": timestamp,
            }
        except Exception as e:
            body = {
                "decision": "ERROR",
                "error": str(e),
                "timestamp": timestamp,
            }
            return {"statusCode": 500, "body": json.dumps(body)}
    else:
        logger.info(
            "Threshold no alcanzado (%d/%d). Pipeline no disparado.",
            new_records,
            threshold,
        )
        body = {
            "decision": "NO_RETRAIN",
            "new_records": new_records,
            "threshold": threshold,
            "timestamp": timestamp,
        }

    return {"statusCode": 200, "body": json.dumps(body)}
