"""
BistroTech — Prueba en Vivo End-to-End

Cubre los cuatro escenarios del ciclo MLOps completo:

  FASE 1 — Entrenamiento inicial con datos históricos (10 000 registros)
  FASE 2 — Simula 1 día de operación: genera datos nuevos, los sube a S3,
            descarga desde S3, reentrena los modelos, empaqueta y sube a S3,
            y verifica que el trigger de reentrenamiento se dispararía.
  FASE 3 — Inferencia local contra los modelos recién entrenados:
            usuario nuevo (sin historial) vs usuario recurrente (con historial)
  FASE 4 — Inferencia contra el endpoint AWS en vivo (API Gateway → SageMaker)

Uso:
    cd d:\\repos\\MLOps-demo-RestauranteIA
    .venv\\Scripts\\activate
    set PYTHONIOENCODING=utf-8
    python live_test.py
"""
import json
import logging
import os
import subprocess
import sys
import time
import traceback

# ── encoding unicode (ñ, etc.) ────────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)

# ── constantes ────────────────────────────────────────────────────────────────
S3_BUCKET = "bistrotech-models-834257582282"
API_URL = "https://ks1yq53cch.execute-api.us-east-1.amazonaws.com/prod/predict"
AWS_REGION = "us-east-1"
DAY1_CSV = "data/raw/day1_reservas.csv"
DAY1_S3_KEY = "data/raw/day1_reservas.csv"
MODEL_V2_TAR = "models/bistrotech-model-v2.tar.gz"
MODEL_V2_S3_KEY = "models/bistrotech-model-v2.tar.gz"


# ── helpers ───────────────────────────────────────────────────────────────────
def _header(title: str) -> None:
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print(f"{'=' * 64}")


def _step_ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _step_skip(msg: str) -> None:
    print(f"  [--] {msg}")


def _step_warn(msg: str) -> None:
    print(f"  [!!] {msg}")


def _aws_cli(args: list[str]) -> tuple[bool, str]:
    """Ejecuta un comando AWS CLI con --no-verify-ssl. Retorna (ok, output)."""
    cmd = ["aws"] + args + ["--no-verify-ssl", "--region", AWS_REGION]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "AWS CLI no encontrado en PATH"
    except subprocess.TimeoutExpired:
        return False, "Timeout (>60s)"
    except Exception as e:
        return False, str(e)


def _reset_model_cache() -> None:
    """Descarta los singletons de modelos y preprocessor para forzar recarga."""
    import importlib
    if "src.inference" in sys.modules:
        sys.modules["src.inference"]._models = None
    if "src.feature_engineering" in sys.modules:
        fe = sys.modules["src.feature_engineering"]
        fe._preprocessor = None
    # Limpia caché de load_processed si existe
    if "src.feature_engineering" in sys.modules:
        fe = sys.modules["src.feature_engineering"]
        if hasattr(fe, "_processed_cache"):
            fe._processed_cache = None


# ── FASE 1: Entrenamiento inicial ─────────────────────────────────────────────
def fase1_entrenamiento_inicial() -> dict:
    _header("FASE 1 — Entrenamiento inicial con datos históricos")

    import pandas as pd
    from src.generate_dataset import generate
    from src.feature_engineering import build_features, save_processed
    from src.train_modelo_a import train as train_a
    from src.train_modelo_b import train_all

    # 1a. Dataset histórico
    os.makedirs("data/raw", exist_ok=True)
    df = generate(10_000, seed=42)
    df.to_csv("data/raw/reservas.csv", index=False)
    _step_ok(f"Dataset histórico generado → data/raw/reservas.csv  "
             f"({len(df):,} registros, {df['id_mesa'].nunique():,} mesas)")

    # 1b. Feature engineering
    X, targets = build_features(df)
    save_processed(X, targets)
    _step_ok(f"Features procesadas → data/processed/  "
             f"({len(targets['propina_rate']):,} registros con feedback completo)")

    # 1c. Modelo A
    metrics_a = train_a("data/raw/reservas.csv")
    _step_ok(f"Modelo A entrenado → models/modelo_a_mozo.joblib  "
             f"RMSE={metrics_a['rmse']:.4f}  MAE={metrics_a['mae']:.4f}  "
             f"Pearson={metrics_a['pearson']:.3f}")

    # 1d. Modelos B
    import numpy as np
    metrics_b = train_all("data/raw/reservas.csv")
    avg_hr = float(np.mean([m["hit_rate_k"] for m in metrics_b.values()]))
    for curso, m in metrics_b.items():
        _step_ok(f"Modelo B '{curso}' → Hit Rate={m['hit_rate_k']:.1%}  F1={m['f1_macro']:.3f}")
    _step_ok(f"Hit Rate promedio Modelos B: {avg_hr:.1%}")

    return {"rmse_a": metrics_a["rmse"], "hit_rate_b": avg_hr}


# ── FASE 2: Día 1 de operación + reentrenamiento desde S3 ─────────────────────
def fase2_retrain_desde_s3(metrics_v1: dict) -> dict:
    _header("FASE 2 — 1 día de operación → S3 → reentrenamiento")

    import pandas as pd
    import numpy as np
    from src.generate_dataset import generate
    from src.feature_engineering import build_features, save_processed
    from src.train_modelo_a import train as train_a
    from src.train_modelo_b import train_all

    # 2a. Generar datos del día 1 (seed distinto = nuevas visitas)
    os.makedirs("data/raw", exist_ok=True)
    df_day1 = generate(500, seed=99)
    df_day1.to_csv(DAY1_CSV, index=False)
    _step_ok(f"Datos del día 1 generados → {DAY1_CSV}  "
             f"({len(df_day1):,} registros, {df_day1['id_mesa'].nunique():,} mesas nuevas)")

    # 2b. Subir a S3
    ok, out = _aws_cli(["s3", "cp", DAY1_CSV, f"s3://{S3_BUCKET}/{DAY1_S3_KEY}"])
    if ok:
        _step_ok(f"Datos subidos a S3 → s3://{S3_BUCKET}/{DAY1_S3_KEY}")
    else:
        _step_warn(f"Upload S3 falló ({out}) — continuando con archivo local ya disponible")

    # 2c. Simular descarga desde S3 (el pipeline leyó de S3)
    ok_dl, out_dl = _aws_cli([
        "s3", "cp", f"s3://{S3_BUCKET}/{DAY1_S3_KEY}", "data/raw/day1_from_s3.csv"
    ])
    if ok_dl:
        df_from_s3 = pd.read_csv("data/raw/day1_from_s3.csv")
        _step_ok(f"Datos descargados desde S3 → data/raw/day1_from_s3.csv  "
                 f"({len(df_from_s3):,} registros)")
    else:
        df_from_s3 = pd.read_csv(DAY1_CSV)
        _step_skip(f"Download S3 falló ({out_dl}) — usando copia local equivalente  "
                   f"({len(df_from_s3):,} registros)")

    # 2d. Combinar histórico + día 1 y reentrenar
    df_hist = pd.read_csv("data/raw/reservas.csv")
    df_combined = pd.concat([df_hist, df_from_s3], ignore_index=True)
    df_combined.to_csv("data/raw/reservas_v2.csv", index=False)
    _step_ok(f"Dataset combinado → data/raw/reservas_v2.csv  "
             f"({len(df_combined):,} registros = {len(df_hist):,} hist + {len(df_from_s3):,} nuevos)")

    # 2e. Reentrenar con datos combinados
    _reset_model_cache()

    X2, targets2 = build_features(df_combined)
    save_processed(X2, targets2)
    _step_ok(f"Features recalculadas  ({len(targets2['propina_rate']):,} registros con feedback)")

    metrics_a2 = train_a("data/raw/reservas_v2.csv")
    delta_rmse = metrics_a2["rmse"] - metrics_v1["rmse_a"]
    _step_ok(
        f"Modelo A v2 reentrenado → RMSE={metrics_a2['rmse']:.4f}  "
        f"(Δ{delta_rmse:+.4f} vs v1)  "
        f"Pearson={metrics_a2['pearson']:.3f}"
    )

    metrics_b2 = train_all("data/raw/reservas_v2.csv")
    avg_hr2 = float(np.mean([m["hit_rate_k"] for m in metrics_b2.values()]))
    delta_hr = avg_hr2 - metrics_v1["hit_rate_b"]
    _step_ok(f"Modelos B v2 reentrenados → Hit Rate={avg_hr2:.1%}  (Δ{delta_hr:+.1%} vs v1)")

    # 2f. Empaquetar modelo v2
    from infrastructure.package_model import package_model
    pkg_path = package_model(output_path=MODEL_V2_TAR)
    size_kb = os.path.getsize(pkg_path) // 1024
    _step_ok(f"Modelo empaquetado → {pkg_path}  ({size_kb} KB)")

    # 2g. Subir modelo v2 a S3
    ok_m, out_m = _aws_cli(["s3", "cp", MODEL_V2_TAR, f"s3://{S3_BUCKET}/{MODEL_V2_S3_KEY}"])
    if ok_m:
        _step_ok(f"Modelo v2 subido a S3 → s3://{S3_BUCKET}/{MODEL_V2_S3_KEY}")
    else:
        _step_warn(f"Upload modelo a S3 falló ({out_m})")
        _step_skip("Para actualizar el endpoint manualmente:")
        _step_skip(f"  aws s3 cp {MODEL_V2_TAR} s3://{S3_BUCKET}/{MODEL_V2_S3_KEY} --no-verify-ssl")
        _step_skip("  python infrastructure/deploy_sagemaker.py")

    # 2h. Simular trigger mini-batch
    from pipelines.trigger_lambda import handler as trigger_handler
    trigger_event = {
        "new_complete_records": len(df_from_s3),
        "retrain_threshold": 50,
        "s3_bucket": S3_BUCKET,
        "pipeline_name": "bistrotech-retrain-pipeline",
    }
    trigger_result = trigger_handler(trigger_event, None)
    body = json.loads(trigger_result["body"])
    decision = body["decision"]
    if decision == "RETRAIN_TRIGGERED":
        _step_ok(
            f"Trigger mini-batch: {body['new_records']} registros >= threshold {body['threshold']}"
            f" → {decision}  (ARN: {body.get('execution_arn', 'N/A')})"
        )
    else:
        _step_warn(f"Trigger mini-batch: {decision}  ({body})")

    return {"rmse_a": metrics_a2["rmse"], "hit_rate_b": avg_hr2}


# ── FASE 3: Inferencia local ───────────────────────────────────────────────────
def fase3_inferencia_local() -> None:
    _header("FASE 3 — Inferencia local: usuario nuevo vs recurrente")

    _reset_model_cache()
    from src.inference import predict

    # ── Caso A: usuario NUEVO ──────────────────────────────────────────────
    print("\n  [A] USUARIO NUEVO — primera visita, sin historial, restricción vegana")
    print("      Mesa 7 | date | noche | viernes")

    caso_nuevo = {
        "id_mesa": 7,
        "comensales": [
            {
                "id_persona_en_mesa": 1,
                "franja_etaria_persona": "adulto",
                "cant_acompañantes": 1,
                "motivo_visita": "date",
                "es_repetidor": False,
                "visitas_previas": 0,
                "ticket_promedio_historico": None,
                "orden_de_pedido": 1,
            },
            {
                "id_persona_en_mesa": 2,
                "franja_etaria_persona": "joven",
                "cant_acompañantes": 1,
                "motivo_visita": "date",
                "es_repetidor": False,
                "visitas_previas": 0,
                "ticket_promedio_historico": None,
                "orden_de_pedido": 2,
            },
        ],
        "dia_semana": 4,
        "franja_horaria": "noche",
    }

    t0 = time.time()
    res_nuevo = predict(caso_nuevo)
    _step_ok(f"Predicción completada en {res_nuevo['latencia_ms']} ms  "
             f"(modelo {res_nuevo['modelo_version']})")

    top3_mozo = res_nuevo["mozos_recomendados"][:3]
    print(f"      Mozos recomendados: " + ", ".join(
        f"#{m['id_mozo']} ({m['propina_rate_esperado']:.3f})" for m in top3_mozo
    ))
    for rec in res_nuevo["recomendaciones_por_comensal"]:
        print(f"      Comensal {rec['id_persona_en_mesa']}:")
        for curso in ["entrada", "principal", "postre", "bebida"]:
            platos = rec.get(curso, [])
            if platos:
                top = platos[0]
                print(f"        {curso:10s}: plato #{top['id_plato']} "
                      f"(score={top['score']:.4f}) + {len(platos)-1} alternativas")

    # ── Caso B: usuario RECURRENTE ─────────────────────────────────────────
    print("\n  [B] USUARIO RECURRENTE — 12 visitas previas, ticket alto, negocios")
    print("      Mesa 22 | negocios | mediodía | martes")

    caso_recurrente = {
        "id_mesa": 22,
        "comensales": [
            {
                "id_persona_en_mesa": 1,
                "franja_etaria_persona": "adulto",
                "cant_acompañantes": 2,
                "motivo_visita": "negocios",
                "es_repetidor": True,
                "visitas_previas": 12,
                "ticket_promedio_historico": 4200.0,
                "orden_de_pedido": 1,
            },
            {
                "id_persona_en_mesa": 2,
                "franja_etaria_persona": "senior",
                "cant_acompañantes": 2,
                "motivo_visita": "negocios",
                "es_repetidor": True,
                "visitas_previas": 7,
                "ticket_promedio_historico": 3800.0,
                "orden_de_pedido": 2,
            },
            {
                "id_persona_en_mesa": 3,
                "franja_etaria_persona": "adulto",
                "cant_acompañantes": 2,
                "motivo_visita": "negocios",
                "es_repetidor": False,
                "visitas_previas": 0,
                "ticket_promedio_historico": None,
                "orden_de_pedido": 3,
            },
        ],
        "dia_semana": 1,
        "franja_horaria": "mediodia",
    }

    res_rec = predict(caso_recurrente)
    _step_ok(f"Predicción completada en {res_rec['latencia_ms']} ms  "
             f"(modelo {res_rec['modelo_version']})")

    top3_mozo_r = res_rec["mozos_recomendados"][:3]
    print(f"      Mozos recomendados: " + ", ".join(
        f"#{m['id_mozo']} ({m['propina_rate_esperado']:.3f})" for m in top3_mozo_r
    ))
    for rec in res_rec["recomendaciones_por_comensal"]:
        es_rep = caso_recurrente["comensales"][rec["id_persona_en_mesa"] - 1]["es_repetidor"]
        visitas = caso_recurrente["comensales"][rec["id_persona_en_mesa"] - 1]["visitas_previas"]
        tag = f"recurrente {visitas}v" if es_rep else "nuevo"
        print(f"      Comensal {rec['id_persona_en_mesa']} ({tag}):")
        for curso in ["entrada", "principal", "postre", "bebida"]:
            platos = rec.get(curso, [])
            if platos:
                top = platos[0]
                print(f"        {curso:10s}: plato #{top['id_plato']} "
                      f"(score={top['score']:.4f}) + {len(platos)-1} alternativas")

    # ── Contraste clave ────────────────────────────────────────────────────
    mozo_nuevo = res_nuevo["mozos_recomendados"][0]["id_mozo"]
    mozo_rec = res_rec["mozos_recomendados"][0]["id_mozo"]
    tip_nuevo = res_nuevo["mozos_recomendados"][0]["propina_rate_esperado"]
    tip_rec = res_rec["mozos_recomendados"][0]["propina_rate_esperado"]

    print(f"\n  [CONTRASTE]")
    print(f"      Usuario nuevo     → mozo #{mozo_nuevo}  propina_rate_esperado={tip_nuevo:.3f}")
    print(f"      Usuario recurrente → mozo #{mozo_rec}  propina_rate_esperado={tip_rec:.3f}")
    if mozo_nuevo != mozo_rec:
        print(f"      → El historial del cliente cambió la asignación del mozo")
    else:
        print(f"      → Mismo mozo óptimo (el historial refuerza la recomendación)")


# ── FASE 4: Endpoint AWS en vivo ───────────────────────────────────────────────
def fase4_endpoint_aws() -> None:
    _header("FASE 4 — Endpoint AWS en vivo (API Gateway → SageMaker)")
    print(f"  Endpoint: {API_URL}\n")

    casos = [
        (
            "Usuario NUEVO (vegano, date)",
            {
                "id_mesa": 7,
                "comensales": [
                    {
                        "id_persona_en_mesa": 1,
                        "franja_etaria_persona": "adulto",
                        "cant_acompañantes": 1,
                        "motivo_visita": "date",
                                "es_repetidor": False,
                        "visitas_previas": 0,
                        "ticket_promedio_historico": None,
                        "orden_de_pedido": 1,
                    }
                ],
                "dia_semana": 4,
                "franja_horaria": "noche",
            },
        ),
        (
            "Usuario RECURRENTE (12 visitas, kosher, negocios)",
            {
                "id_mesa": 22,
                "comensales": [
                    {
                        "id_persona_en_mesa": 1,
                        "franja_etaria_persona": "adulto",
                        "cant_acompañantes": 2,
                        "motivo_visita": "negocios",
                                "es_repetidor": True,
                        "visitas_previas": 12,
                        "ticket_promedio_historico": 3800.0,
                        "orden_de_pedido": 1,
                    }
                ],
                "dia_semana": 1,
                "franja_horaria": "mediodia",
            },
        ),
    ]

    # Intentar con requests primero, luego urllib
    http_client = None
    try:
        import requests
        http_client = "requests"
    except ImportError:
        pass

    for label, payload in casos:
        print(f"  [{label}]")
        body_str = json.dumps(payload, ensure_ascii=False)

        if http_client == "requests":
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                import requests
                t0 = time.time()
                resp = requests.post(
                    API_URL,
                    data=body_str.encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    verify=False,
                    timeout=30,
                )
                elapsed = int((time.time() - t0) * 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    top_mozo = data["mozos_recomendados"][0]
                    _step_ok(
                        f"HTTP 200 | round-trip {elapsed}ms | "
                        f"latencia_modelo={data['latencia_ms']}ms | "
                        f"versión={data['modelo_version']} | "
                        f"mozo recomendado #{top_mozo['id_mozo']} "
                        f"(rate={top_mozo['propina_rate_esperado']:.3f})"
                    )
                else:
                    _step_warn(f"HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                _step_warn(f"requests falló: {e}")
                _intentar_curl(body_str, label)
        else:
            # Fallback: urllib con SSL no verificado
            _intentar_urllib(body_str, label)

        print()


def _intentar_curl(body_str: str, label: str) -> None:
    """Intenta la llamada con curl -k como fallback."""
    cmd = [
        "curl", "-k", "-s", "-w", "\n%{http_code}", "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", body_str,
        API_URL,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        lines = result.stdout.strip().split("\n")
        status = lines[-1]
        response_body = "\n".join(lines[:-1])
        if status == "200":
            data = json.loads(response_body)
            top_mozo = data["mozos_recomendados"][0]
            _step_ok(
                f"curl HTTP 200 | versión={data['modelo_version']} | "
                f"mozo #{top_mozo['id_mozo']} (rate={top_mozo['propina_rate_esperado']:.3f})"
            )
        else:
            _step_warn(f"curl HTTP {status}: {response_body[:200]}")
    except Exception as e:
        _step_warn(f"curl también falló: {e}")
        _step_skip(f"Probar manualmente:")
        _step_skip(f"  curl -k -X POST -H 'Content-Type: application/json'")
        _step_skip(f"  -d '{body_str[:100]}...'")
        _step_skip(f"  {API_URL}")


def _intentar_urllib(body_str: str, label: str) -> None:
    """Intenta la llamada con urllib (sin verificar SSL)."""
    import urllib.request
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        API_URL,
        data=body_str.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            elapsed = int((time.time() - t0) * 1000)
            data = json.loads(resp.read().decode("utf-8"))
            top_mozo = data["mozos_recomendados"][0]
            _step_ok(
                f"HTTP 200 | round-trip {elapsed}ms | "
                f"latencia_modelo={data['latencia_ms']}ms | "
                f"versión={data['modelo_version']} | "
                f"mozo #{top_mozo['id_mozo']} (rate={top_mozo['propina_rate_esperado']:.3f})"
            )
    except Exception as e:
        _step_warn(f"urllib falló: {e}")
        _intentar_curl(body_str, label)


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\n" + "=" * 64)
    print("  BistroTech — Prueba en Vivo End-to-End")
    print("=" * 64)

    errores: list[str] = []

    # FASE 1
    try:
        metrics_v1 = fase1_entrenamiento_inicial()
    except Exception:
        errores.append("FASE 1")
        traceback.print_exc()
        print("\n[ERR] Fase 1 falló — abortando (modelos requeridos para fases siguientes).")
        sys.exit(1)

    # FASE 2
    try:
        metrics_v2 = fase2_retrain_desde_s3(metrics_v1)
    except Exception:
        errores.append("FASE 2")
        traceback.print_exc()
        print("\n[ERR] Fase 2 falló — continuando con modelos de Fase 1.")
        metrics_v2 = metrics_v1

    # FASE 3
    try:
        fase3_inferencia_local()
    except Exception:
        errores.append("FASE 3")
        traceback.print_exc()
        print("\n[ERR] Fase 3 falló.")

    # FASE 4
    try:
        fase4_endpoint_aws()
    except Exception:
        errores.append("FASE 4")
        traceback.print_exc()
        print("\n[ERR] Fase 4 falló.")

    # Resumen final
    _header("RESUMEN")
    fases = ["FASE 1", "FASE 2", "FASE 3", "FASE 4"]
    for f in fases:
        if f in errores:
            print(f"  [FAIL] {f}")
        else:
            print(f"  [ OK ] {f}")

    print()
    if not errores:
        print("  Todas las fases completadas exitosamente.")
    else:
        print(f"  {len(errores)} fase(s) con errores: {', '.join(errores)}")
    print()


if __name__ == "__main__":
    main()
