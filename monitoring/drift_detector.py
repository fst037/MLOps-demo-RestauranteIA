"""
Detección de model drift para BistroTech usando Population Stability Index (PSI).

PSI < 0.1  → sin drift (estable)
PSI 0.1-0.2 → drift leve (monitorear)
PSI > 0.2  → drift severo (alertar, considerar reentrenamiento)
"""
import logging
import os
import numpy as np

logger = logging.getLogger(__name__)

PSI_STABLE_THRESHOLD = 0.1
PSI_ALERT_THRESHOLD = 0.2
N_BINS = 10


def _psi_bins(baseline: list[float], n_bins: int) -> tuple[np.ndarray, np.ndarray]:
    """Calcula los bordes de bins a partir del baseline."""
    arr = np.array(baseline, dtype=float)
    percentiles = np.linspace(0, 100, n_bins + 1)
    bins = np.unique(np.percentile(arr, percentiles))
    if len(bins) < 2:
        bins = np.array([arr.min() - 1e-9, arr.max() + 1e-9])
    return bins


def calculate_drift(
    predictions_recent: list[float],
    predictions_baseline: list[float],
    n_bins: int = N_BINS,
) -> float:
    """
    Calcula el Population Stability Index (PSI) entre distribuciones de predicciones.

    PSI = sum((actual% - expected%) * ln(actual% / expected%))

    Args:
        predictions_recent: predicciones del período reciente (ventana actual).
        predictions_baseline: predicciones de referencia (entrenamiento o semana anterior).
        n_bins: número de buckets para el histograma.

    Returns:
        Valor PSI (float >= 0).
    """
    if len(predictions_recent) < 10 or len(predictions_baseline) < 10:
        logger.warning("Muestras insuficientes para calcular PSI con confianza.")
        return 0.0

    baseline = np.array(predictions_baseline, dtype=float)
    recent = np.array(predictions_recent, dtype=float)

    bins = _psi_bins(list(baseline), n_bins)

    def _safe_freq(arr: np.ndarray) -> np.ndarray:
        counts, _ = np.histogram(arr, bins=bins)
        freq = counts / len(arr)
        freq = np.where(freq == 0, 1e-6, freq)
        return freq

    freq_baseline = _safe_freq(baseline)
    freq_recent = _safe_freq(recent)

    psi = float(np.sum((freq_recent - freq_baseline) * np.log(freq_recent / freq_baseline)))
    logger.debug("PSI calculado: %.4f (%d bins)", psi, len(bins) - 1)
    return round(psi, 6)


def should_alert(psi_score: float, threshold: float = PSI_ALERT_THRESHOLD) -> bool:
    """
    Determina si el PSI justifica una alerta de drift severo.

    Niveles:
      PSI < 0.1  → Estable — sin acción requerida.
      0.1-0.2    → Drift leve — monitorear de cerca.
      > 0.2      → Drift severo — considerar reentrenamiento inmediato.

    Args:
        psi_score: valor PSI calculado.
        threshold: umbral para drift severo (default 0.2).

    Returns:
        True si se debe disparar una alerta.
    """
    if psi_score < PSI_STABLE_THRESHOLD:
        level = "ESTABLE"
        alert = False
    elif psi_score < threshold:
        level = "LEVE"
        alert = False
    else:
        level = "SEVERO"
        alert = True

    logger.info(
        "PSI=%.4f → Drift %s%s",
        psi_score,
        level,
        " ⚠️ ALERTA" if alert else "",
    )
    return alert


def log_drift_metric(psi_score: float, metric_name: str = "propina_rate_psi") -> None:
    """
    Envía la métrica de drift a CloudWatch.

    Usa boto3 para publicar una custom metric en el namespace 'BistroTech/ModelDrift'.
    Si boto3 no está disponible o no hay credenciales, loguea localmente.

    Args:
        psi_score: valor PSI a reportar.
        metric_name: nombre de la dimensión en CloudWatch.
    """
    namespace = "BistroTech/ModelDrift"
    try:
        import boto3
        cw = boto3.client(
            "cloudwatch",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
        cw.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": psi_score,
                    "Unit": "None",
                    "Dimensions": [
                        {"Name": "Model", "Value": "BistroTech"},
                        {"Name": "Stage", "Value": "Production"},
                    ],
                }
            ],
        )
        logger.info(
            "Métrica '%s'=%.4f enviada a CloudWatch (%s).", metric_name, psi_score, namespace
        )
    except ImportError:
        logger.info(
            "[LOCAL] Métrica drift '%s'=%.4f (CloudWatch no disponible).",
            metric_name,
            psi_score,
        )
    except Exception as e:
        logger.warning(
            "No se pudo enviar a CloudWatch: %s. PSI=%s métrica='%s'",
            e,
            psi_score,
            metric_name,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    np.random.seed(42)

    baseline = list(np.random.normal(0.15, 0.04, 500))
    stable = list(np.random.normal(0.15, 0.04, 200))
    drifted = list(np.random.normal(0.08, 0.06, 200))

    print("=== PSI Estable ===")
    psi_s = calculate_drift(stable, baseline)
    print(f"PSI: {psi_s:.4f}")
    should_alert(psi_s)
    log_drift_metric(psi_s, "propina_rate_psi")

    print("\n=== PSI Drifted ===")
    psi_d = calculate_drift(drifted, baseline)
    print(f"PSI: {psi_d:.4f}")
    should_alert(psi_d)
    log_drift_metric(psi_d, "propina_rate_psi")
