"""
Interfaz con SageMaker Feature Store para BistroTech.

Abstrae las operaciones de lectura/escritura del Feature Store online y offline.
Tiene fallback local cuando no hay credenciales AWS configuradas.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

FEATURE_GROUP_NAME = os.environ.get("FEATURE_GROUP_NAME", "bistrotech-comensales-fg")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ.get("S3_BUCKET", "bistrotech-models")


def _get_feature_store_client():
    import boto3
    return boto3.client(
        "sagemaker-featurestore-runtime",
        region_name=AWS_REGION,
    )


def put_record(record: dict, feature_group_name: str = FEATURE_GROUP_NAME) -> bool:
    """
    Escribe un registro en el Feature Store online.

    Args:
        record: dict con los campos del Feature Group.
                Debe incluir 'id_registro' (identifier) y 'event_time'.
        feature_group_name: nombre del Feature Group.

    Returns:
        True si se escribió correctamente, False si falló con fallback.
    """
    if "event_time" not in record:
        record["event_time"] = datetime.now(timezone.utc).isoformat()

    try:
        client = _get_feature_store_client()
        feature_list = [
            {"FeatureName": k, "ValueAsString": str(v)}
            for k, v in record.items()
            if v is not None
        ]
        client.put_record(
            FeatureGroupName=feature_group_name,
            Record=feature_list,
        )
        logger.debug("Registro %s escrito en Feature Store.", record.get("id_registro"))
        return True
    except ImportError:
        logger.warning("boto3 no disponible — registro no persistido en Feature Store.")
        return False
    except Exception as e:
        logger.error("Error al escribir en Feature Store: %s", e)
        return False


def get_record(
    id_registro: int,
    feature_group_name: str = FEATURE_GROUP_NAME,
) -> Optional[dict]:
    """
    Lee un registro del Feature Store online por ID.

    Args:
        id_registro: identificador único del registro.
        feature_group_name: nombre del Feature Group.

    Returns:
        dict con el registro, o None si no existe o hay error.
    """
    try:
        client = _get_feature_store_client()
        response = client.get_record(
            FeatureGroupName=feature_group_name,
            RecordIdentifierValueAsString=str(id_registro),
        )
        record = {feat["FeatureName"]: feat["ValueAsString"] for feat in response["Record"]}
        return record
    except ImportError:
        logger.warning("boto3 no disponible — Feature Store no accesible.")
        return None
    except Exception as e:
        logger.warning("No se pudo leer registro %d: %s", id_registro, e)
        return None


def batch_put_records(
    df: pd.DataFrame,
    feature_group_name: str = FEATURE_GROUP_NAME,
) -> int:
    """
    Escribe un DataFrame completo en el Feature Store en batch.

    Optimizado para ingesta inicial o sincronización de histórico.

    Args:
        df: DataFrame con los registros a persistir.
        feature_group_name: nombre del Feature Group.

    Returns:
        Número de registros escritos exitosamente.
    """
    try:
        import sagemaker
        from sagemaker.feature_store.feature_group import FeatureGroup

        sess = sagemaker.Session()
        fg = FeatureGroup(name=feature_group_name, sagemaker_session=sess)
        fg.ingest(data_frame=df, max_workers=4, wait=True)
        logger.info("Batch ingest: %d registros escritos en '%s'.", len(df), feature_group_name)
        return len(df)
    except ImportError:
        logger.warning("sagemaker SDK no disponible — batch ingest omitido.")
        return 0
    except Exception as e:
        logger.error("Error en batch ingest: %s", e)
        return 0


def query_offline_store(
    query: str,
    output_location: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Ejecuta una query Athena sobre el Feature Store offline.

    Args:
        query: SQL query para Athena.
        output_location: URI S3 para resultados (default: s3://bucket/athena-results/).

    Returns:
        DataFrame con los resultados, o None si falla.
    """
    if output_location is None:
        output_location = f"s3://{S3_BUCKET}/athena-results/"

    try:
        import sagemaker
        from sagemaker.feature_store.feature_group import FeatureGroup

        sess = sagemaker.Session()
        fg = FeatureGroup(name=FEATURE_GROUP_NAME, sagemaker_session=sess)
        query_obj = fg.athena_query()
        query_obj.run(query_string=query, output_location=output_location)
        query_obj.wait()
        df = query_obj.as_dataframe()
        logger.info("Query Athena completada: %d filas.", len(df))
        return df
    except ImportError:
        logger.warning("sagemaker SDK no disponible — query offline omitida.")
        return None
    except Exception as e:
        logger.error("Error en query offline: %s", e)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_record = {
        "id_registro": 99999,
        "id_mesa": 1,
        "franja_horaria": "noche",
        "propina_rate": 0.15,
    }
    success = put_record(test_record)
    print(f"put_record: {'OK' if success else 'FALLBACK (sin AWS)'}")

    retrieved = get_record(99999)
    print(f"get_record: {retrieved or 'N/A (sin AWS)'}")
