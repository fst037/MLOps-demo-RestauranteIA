"""
Configura los Kinesis Data Streams para BistroTech.

Streams:
  - bistrotech-eventos: eventos en tiempo real (reservas, pedidos).
  - bistrotech-feedback: feedback post-servicio (propinas, likes, proporciones).
"""
import logging
import os

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
STREAM_EVENTOS = os.environ.get("KINESIS_STREAM_EVENTOS", "bistrotech-eventos")
STREAM_FEEDBACK = os.environ.get("KINESIS_STREAM_FEEDBACK", "bistrotech-feedback")
SHARD_COUNT = int(os.environ.get("KINESIS_SHARD_COUNT", 1))


def create_stream(stream_name: str, shard_count: int = SHARD_COUNT) -> dict:
    """
    Crea un Kinesis Data Stream si no existe.

    Args:
        stream_name: nombre del stream.
        shard_count: número de shards (capacidad).

    Returns:
        dict con 'stream_name' y 'arn'.
    """
    try:
        import boto3
        kinesis = boto3.client("kinesis", region_name=AWS_REGION)

        try:
            kinesis.create_stream(StreamName=stream_name, ShardCount=shard_count)
            kinesis.get_waiter("stream_exists").wait(StreamName=stream_name)
            logger.info("Stream '%s' creado con %d shard(s).", stream_name, shard_count)
        except kinesis.exceptions.ResourceInUseException:
            logger.info("Stream '%s' ya existe.", stream_name)

        desc = kinesis.describe_stream_summary(StreamName=stream_name)
        arn = desc["StreamDescriptionSummary"]["StreamARN"]
        return {"stream_name": stream_name, "arn": arn}

    except ImportError:
        logger.error("boto3 no instalado.")
        raise
    except Exception as e:
        logger.error("Error al crear stream '%s': %s", stream_name, e)
        raise


def setup_all() -> dict:
    """
    Crea todos los streams requeridos por BistroTech.

    Returns:
        dict con los ARNs de los streams creados.
    """
    result = {}
    for stream_name in [STREAM_EVENTOS, STREAM_FEEDBACK]:
        info = create_stream(stream_name)
        result[stream_name] = info["arn"]
        logger.info("Stream configurado: %s → %s", stream_name, info["arn"])
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not os.environ.get("AWS_REGION"):
        print("Configurar variables de entorno:")
        print("  export AWS_REGION=us-east-1")
        print("  export KINESIS_STREAM_EVENTOS=bistrotech-eventos")
        print("  export KINESIS_STREAM_FEEDBACK=bistrotech-feedback")
    else:
        arns = setup_all()
        for name, arn in arns.items():
            print(f"{name}: {arn}")
