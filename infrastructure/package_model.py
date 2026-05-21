"""
Empaqueta los artefactos del modelo y los sube a S3 para SageMaker.

Genera un .tar.gz con: modelos joblib, feature names, preprocessor y version.txt.
"""
import logging
import os
import tarfile
import tempfile

logger = logging.getLogger(__name__)

S3_BUCKET = os.environ.get("S3_BUCKET", "bistrotech-models")
S3_KEY = os.environ.get("MODEL_S3_KEY", "models/bistrotech-model.tar.gz")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1.0")

MODEL_FILES = [
    # Native XGBoost binary format (version-neutral, works with container 1.7.x)
    "models/modelo_a_mozo.ubj",
    "models/feature_names_a.json",
    "models/modelo_b_entrada.ubj",
    "models/modelo_b_principal.ubj",
    "models/modelo_b_postre.ubj",
    "models/modelo_b_bebida.ubj",
    "models/label_encoder_entrada.json",
    "models/label_encoder_principal.json",
    "models/label_encoder_postre.json",
    "models/label_encoder_bebida.json",
    "data/processed/preprocessor.json",
]

# Packaged as code/inference.py so SageMaker XGBoost container uses script mode.
INFERENCE_SCRIPT = "infrastructure/sagemaker_inference.py"


def package_model(output_path: str = "models/bistrotech-model.tar.gz") -> str:
    """
    Crea un archivo .tar.gz con todos los artefactos del modelo.

    Args:
        output_path: ruta local de salida del archivo comprimido.

    Returns:
        Ruta del archivo generado.
    """
    with tarfile.open(output_path, "w:gz") as tar:
        for fpath in MODEL_FILES:
            if os.path.exists(fpath):
                arcname = os.path.basename(fpath)
                tar.add(fpath, arcname=arcname)
                logger.info("Añadido: %s → %s", fpath, arcname)
            else:
                logger.warning("Archivo no encontrado (omitido): %s", fpath)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(MODEL_VERSION)
            tmp_version = f.name
        tar.add(tmp_version, arcname="version.txt")
        os.unlink(tmp_version)

        if os.path.exists(INFERENCE_SCRIPT):
            tar.add(INFERENCE_SCRIPT, arcname="code/inference.py")
            logger.info("Añadido: %s → code/inference.py", INFERENCE_SCRIPT)
        else:
            logger.warning("Inference script no encontrado (omitido): %s", INFERENCE_SCRIPT)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("")
            tmp_req = f.name
        tar.add(tmp_req, arcname="code/requirements.txt")
        os.unlink(tmp_req)
        logger.info("Añadido: code/requirements.txt (vacío — xgboost pre-instalado en container)")

    logger.info("Modelo empaquetado en %s", output_path)
    return output_path


def upload_to_s3(local_path: str, bucket: str = S3_BUCKET, key: str = S3_KEY) -> str:
    """
    Sube el archivo empaquetado a S3.

    Args:
        local_path: ruta local del .tar.gz.
        bucket: nombre del bucket S3.
        key: clave S3 de destino.

    Returns:
        URI S3 del archivo subido.
    """
    try:
        import boto3
        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        s3.upload_file(local_path, bucket, key)
        s3_uri = f"s3://{bucket}/{key}"
        logger.info("Modelo subido a %s", s3_uri)
        return s3_uri
    except ImportError:
        logger.error("boto3 no instalado.")
        raise
    except Exception as e:
        logger.error("Error al subir a S3: %s", e)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    local_pkg = package_model()
    if os.environ.get("S3_BUCKET"):
        uri = upload_to_s3(local_pkg)
        print(f"Model URI: {uri}")
    else:
        print(f"Empaquetado local: {local_pkg}")
        print("Para subir a S3: export S3_BUCKET=tu-bucket && python infrastructure/package_model.py")
