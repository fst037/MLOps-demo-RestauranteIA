"""
Tests de integración del endpoint SageMaker para BistroTech.

Requieren ENDPOINT_NAME y credenciales AWS configuradas.
Ejecutar solo en entornos con acceso a AWS.

Ejecutar: pytest tests/test_endpoint.py -v -m integration
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME", "bistrotech-endpoint-v1")
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Tests de integración deshabilitados. Setear RUN_INTEGRATION_TESTS=1 para habilitar.",
)

SAMPLE_PAYLOAD = {
    "id_mesa": 42,
    "comensales": [
        {
            "id_persona_en_mesa": 1,
            "franja_etaria_persona": "adulto",
            "cant_acompañantes": 1,
            "motivo_visita": "casual",
            "restriccion_alimentaria": "ninguna",
            "es_repetidor": True,
            "visitas_previas": 3,
            "ticket_promedio_historico": 2000.0,
            "orden_de_pedido": 1,
        }
    ],
    "dia_semana": 2,
    "franja_horaria": "noche",
}


@pytest.fixture(scope="module")
def sm_runtime():
    """Cliente boto3 para invocar el endpoint."""
    try:
        import boto3
        return boto3.client(
            "sagemaker-runtime",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    except ImportError:
        pytest.skip("boto3 no disponible.")


def test_endpoint_health(sm_runtime):
    """El endpoint debe responder sin errores 5xx."""
    response = sm_runtime.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps(SAMPLE_PAYLOAD),
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200, (
        f"Endpoint retornó código {response['ResponseMetadata']['HTTPStatusCode']}"
    )


def test_endpoint_output_format(sm_runtime):
    """El output del endpoint debe tener el formato exacto de la API."""
    response = sm_runtime.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps(SAMPLE_PAYLOAD),
    )
    result = json.loads(response["Body"].read())

    assert "id_mesa" in result
    assert "mozos_recomendados" in result
    assert "recomendaciones_por_comensal" in result
    assert "modelo_version" in result
    assert "latencia_ms" in result
    assert isinstance(result["latencia_ms"], int)


def test_endpoint_latency(sm_runtime):
    """La latencia p99 del endpoint debe ser menor a 500ms."""
    import time

    latencies = []
    for _ in range(5):
        t0 = time.time()
        sm_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType="application/json",
            Body=json.dumps(SAMPLE_PAYLOAD),
        )
        latencies.append((time.time() - t0) * 1000)

    import numpy as np
    p99 = float(np.percentile(latencies, 99))
    assert p99 < 500, f"Latencia p99={p99:.0f}ms supera el umbral de 500ms."
