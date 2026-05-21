"""
Entry point SageMaker para BistroTech.

Implementa las funciones requeridas por el SageMaker Python SDK:
  model_fn, input_fn, predict_fn, output_fn
"""
import io
import json
import logging
import os

import joblib

logger = logging.getLogger(__name__)


def model_fn(model_dir: str) -> dict:
    """
    Carga los modelos desde el directorio de artefactos de SageMaker.

    SageMaker descomprime el .tar.gz del modelo en model_dir antes de llamar esta función.

    Args:
        model_dir: directorio donde se encuentran los artefactos.

    Returns:
        dict con todos los modelos y encoders cargados.
    """
    import sys
    sys.path.insert(0, model_dir)

    models = {}
    try:
        models["modelo_a"] = joblib.load(os.path.join(model_dir, "modelo_a_mozo.joblib"))
        with open(os.path.join(model_dir, "feature_names_a.json")) as f:
            import json as _json
            models["feature_names_a"] = _json.load(f)
        logger.info("Modelo A cargado.")
    except FileNotFoundError as e:
        logger.warning("Modelo A no encontrado: %s", e)

    for curso in ["entrada", "principal", "postre", "bebida"]:
        try:
            models[f"modelo_b_{curso}"] = joblib.load(
                os.path.join(model_dir, f"modelo_b_{curso}.joblib")
            )
            models[f"label_encoder_{curso}"] = joblib.load(
                os.path.join(model_dir, f"label_encoder_{curso}.joblib")
            )
        except FileNotFoundError as e:
            logger.warning("Modelo B '%s' no encontrado: %s", curso, e)

    try:
        models["preprocessor"] = joblib.load(
            os.path.join(model_dir, "preprocessor.joblib")
        )
    except FileNotFoundError as e:
        logger.warning("Preprocessor no encontrado: %s", e)

    version_file = os.path.join(model_dir, "version.txt")
    models["version"] = open(version_file).read().strip() if os.path.exists(version_file) else "v1.0"

    logger.info("Todos los modelos cargados desde %s", model_dir)
    return models


def input_fn(request_body: str, content_type: str = "application/json") -> dict:
    """
    Deserializa el request body.

    Args:
        request_body: cuerpo del request HTTP.
        content_type: tipo de contenido del request.

    Returns:
        dict con el contexto de la mesa.
    """
    if content_type == "application/json":
        return json.loads(request_body)
    raise ValueError(f"Content type no soportado: {content_type}")


def predict_fn(input_data: dict, model: dict) -> dict:
    """
    Ejecuta la predicción usando los modelos cargados.

    Args:
        input_data: dict con el contexto de la mesa (formato API).
        model: dict con los modelos cargados por model_fn.

    Returns:
        dict con el output completo de la API.
    """
    import sys
    import os
    sys.path.insert(0, "/opt/ml/code")

    from src.inference import predict as _predict
    import src.inference as inf_mod
    inf_mod._models = model

    if "preprocessor" in model:
        import src.feature_engineering as fe_mod
        fe_mod._set_preprocessor(model["preprocessor"])

    return _predict(input_data)


def output_fn(prediction: dict, accept: str = "application/json") -> tuple:
    """
    Serializa el output de la predicción.

    Args:
        prediction: dict con el resultado de predict_fn.
        accept: tipo de contenido aceptado por el cliente.

    Returns:
        tuple (body_str, content_type)
    """
    if accept == "application/json":
        return json.dumps(prediction, ensure_ascii=False), "application/json"
    raise ValueError(f"Accept type no soportado: {accept}")
