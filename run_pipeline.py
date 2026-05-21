"""
Orquestador local del pipeline completo de BistroTech.

Ejecuta en orden:
  1. generate_dataset   → data/raw/reservas.csv
  2. feature_engineering → data/processed/
  3. train_modelo_a     → models/modelo_a_mozo.joblib
  4. train_modelo_b x4  → models/modelo_b_*.joblib
  5. predict() de prueba (3 casos)
  6. simulate_minibatch_trigger()
"""
import json
import sys
import traceback


def _step(label: str, fn, *args, **kwargs):
    """Ejecuta un paso y maneja errores con mensaje claro."""
    try:
        result = fn(*args, **kwargs)
        return result
    except Exception as e:
        print(f"\n[ERR] Error en paso '{label}': {e}")
        traceback.print_exc()
        sys.exit(1)


def step1_generate():
    from src.generate_dataset import generate, print_stats
    import os
    os.makedirs("data/raw", exist_ok=True)
    df = generate(10_000)
    df.to_csv("data/raw/reservas.csv", index=False)
    n_mesas = df["id_mesa"].nunique()
    print(f"[OK] Dataset generado ({len(df)} registros, {n_mesas} mesas)")
    return df


def step2_features(df=None):
    import pandas as pd
    from src.feature_engineering import build_features, save_processed
    if df is None:
        df = pd.read_csv("data/raw/reservas.csv")
    X, targets = build_features(df)
    save_processed(X, targets)
    n_feedback = len(targets["propina_rate"])
    print(f"[OK] Features procesadas ({n_feedback} registros con feedback completo)")
    return X, targets


def step3_modelo_a():
    from src.train_modelo_a import train
    metrics = train("data/raw/reservas.csv")
    print(f"[OK] Modelo A entrenado — RMSE: {metrics['rmse']:.4f}")
    return metrics


def step4_modelo_b():
    import numpy as np
    from src.train_modelo_b import train_all
    all_metrics = train_all("data/raw/reservas.csv")
    avg_hr = float(np.mean([m["hit_rate_k"] for m in all_metrics.values()]))
    print(f"[OK] Modelos B entrenados — Hit Rate promedio: {avg_hr:.1%}")
    return all_metrics


def step5_predict():
    from src.inference import predict

    casos = [
        {
            "id_mesa": 42,
            "comensales": [
                {
                    "id_persona_en_mesa": 1,
                    "franja_etaria_persona": "adulto",
                    "cant_acompañantes": 3,
                    "motivo_visita": "negocios",
                    "restriccion_alimentaria": "ninguna",
                    "es_repetidor": True,
                    "visitas_previas": 5,
                    "ticket_promedio_historico": 3200.0,
                    "orden_de_pedido": 1,
                }
            ],
            "dia_semana": 1,
            "franja_horaria": "mediodia",
        },
        {
            "id_mesa": 15,
            "comensales": [
                {
                    "id_persona_en_mesa": i,
                    "franja_etaria_persona": ["joven", "adulto", "adulto", "senior"][i - 1],
                    "cant_acompañantes": 3,
                    "motivo_visita": "cumpleaños",
                    "restriccion_alimentaria": "ninguna",
                    "es_repetidor": i > 2,
                    "visitas_previas": 4 if i > 2 else 0,
                    "ticket_promedio_historico": 2500.0 if i > 2 else None,
                    "orden_de_pedido": i,
                }
                for i in range(1, 5)
            ],
            "dia_semana": 6,
            "franja_horaria": "noche",
        },
        {
            "id_mesa": 8,
            "comensales": [
                {
                    "id_persona_en_mesa": 1,
                    "franja_etaria_persona": "adulto",
                    "cant_acompañantes": 1,
                    "motivo_visita": "date",
                    "restriccion_alimentaria": "vegano",
                    "es_repetidor": False,
                    "visitas_previas": 0,
                    "ticket_promedio_historico": None,
                    "orden_de_pedido": 1,
                },
                {
                    "id_persona_en_mesa": 2,
                    "franja_etaria_persona": "adulto",
                    "cant_acompañantes": 1,
                    "motivo_visita": "date",
                    "restriccion_alimentaria": "ninguna",
                    "es_repetidor": True,
                    "visitas_previas": 8,
                    "ticket_promedio_historico": 4500.0,
                    "orden_de_pedido": 2,
                },
            ],
            "dia_semana": 5,
            "franja_horaria": "noche",
        },
    ]

    nombres = ["Almuerzo de negocios (1 comensal)", "Cumpleaños (4 comensales)", "Date con vegano (2 comensales)"]
    for i, (caso, nombre) in enumerate(zip(casos, nombres), 1):
        resultado = predict(caso)
        top_mozo = resultado["mozos_recomendados"][0]
        print(
            f"[OK] Caso {i} ({nombre}): mozo recomendado #{top_mozo['id_mozo']} "
            f"(propina_rate_esperado={top_mozo['propina_rate_esperado']:.3f}) "
            f"| latencia={resultado['latencia_ms']}ms"
        )
    return casos


def simulate_minibatch_trigger():
    """Simula la llegada de 50+ registros completos y el trigger del pipeline."""
    from pipelines.trigger_lambda import handler

    event = {
        "new_complete_records": 55,
        "retrain_threshold": 50,
        "s3_bucket": "bistrotech-local",
    }
    result = handler(event, None)
    body = json.loads(result["body"])
    decision = body.get("decision", "?")
    if decision == "RETRAIN_TRIGGERED":
        print(
            f"[OK] Trigger mini-batch: {body['new_records']} registros >= threshold {body['threshold']}"
            f" → Pipeline disparado ({body.get('execution_arn', 'N/A')})"
        )
    else:
        print(f"[INFO] Trigger mini-batch: decisión={decision}")
    return body


def main():
    print("=" * 60)
    print("BistroTech — Pipeline local completo")
    print("=" * 60)

    _step("1. Generación de dataset", step1_generate)
    _step("2. Feature engineering", step2_features)
    _step("3. Entrenamiento Modelo A", step3_modelo_a)
    _step("4. Entrenamiento Modelos B", step4_modelo_b)
    _step("5. Predicciones de prueba", step5_predict)
    _step("6. Simulación trigger mini-batch", simulate_minibatch_trigger)

    print("\n" + "=" * 60)
    print("Pipeline completado exitosamente.")
    print("=" * 60)


if __name__ == "__main__":
    main()
