# -*- coding: utf-8 -*-
"""
SageMaker serving script for BistroTech — version-neutral artifact loading.

Loads XGBoost models from native .ubj format and preprocessors from JSON,
avoiding any pickle/sklearn version mismatch with the 1.7 container.
"""
import json
import logging
import os
import time

import numpy as np
import pandas as pd
import xgboost as xgb

logger = logging.getLogger(__name__)

CAT_FEATURES = {
    "franja_horaria":          ["mediodia", "noche", "tarde"],
    "franja_etaria_persona":   ["adulto", "joven", "senior"],
    "motivo_visita":           ["casual", "cumpleaños", "date", "negocios", "turista"],
    "restriccion_alimentaria": ["celiaco", "kosher", "ninguna", "vegano", "vegetariano"],
}

DISH_RESTRICTIONS: dict = {
    1:  ["ninguna", "vegetariano", "vegano", "celiaco", "kosher"],
    2:  ["ninguna", "vegetariano", "celiaco", "kosher"],
    3:  ["ninguna", "kosher"],
    4:  ["ninguna", "kosher"],
    5:  ["ninguna", "vegetariano", "vegano", "celiaco"],
    6:  ["ninguna", "vegetariano", "vegano"],
    7:  ["ninguna", "celiaco"],
    8:  ["ninguna", "vegetariano"],
    9:  ["ninguna", "kosher"],
    10: ["ninguna", "kosher"],
    11: ["ninguna"],
    12: ["ninguna", "vegetariano", "celiaco"],
    13: ["ninguna", "vegetariano", "vegano", "celiaco"],
    14: ["ninguna", "celiaco"],
    15: ["ninguna", "kosher"],
    16: ["ninguna", "vegetariano"],
    17: ["ninguna", "kosher"],
    18: ["ninguna", "vegetariano", "vegano"],
    19: ["ninguna", "vegetariano", "vegano", "celiaco"],
    20: ["ninguna"],
    21: ["ninguna", "vegetariano", "vegano", "celiaco"],
    22: ["ninguna", "vegetariano"],
    23: ["ninguna", "vegetariano", "celiaco"],
    24: ["ninguna", "vegetariano"],
    25: ["ninguna", "vegetariano", "vegano"],
    26: ["ninguna", "vegetariano", "vegano", "celiaco", "kosher"],
    27: ["ninguna", "vegetariano", "vegano", "celiaco", "kosher"],
    28: ["ninguna", "vegetariano", "vegano", "celiaco", "kosher"],
    29: ["ninguna", "vegetariano", "vegano", "celiaco", "kosher"],
    30: ["ninguna", "vegetariano", "vegano", "celiaco", "kosher"],
}

CURSO_DISH_RANGE: dict = {
    "entrada":   range(1, 9),
    "principal": range(9, 21),
    "postre":    range(21, 26),
    "bebida":    range(26, 31),
}


# ---------------------------------------------------------------------------
# SageMaker hook — load all artifacts from /opt/ml/model/
# ---------------------------------------------------------------------------
def model_fn(model_dir: str) -> dict:
    models: dict = {}

    booster_a = xgb.Booster()
    booster_a.load_model(os.path.join(model_dir, "modelo_a_mozo.ubj"))
    models["booster_a"] = booster_a

    with open(os.path.join(model_dir, "feature_names_a.json"), encoding="utf-8") as f:
        models["feature_names_a"] = json.load(f)

    for curso in ["entrada", "principal", "postre", "bebida"]:
        b = xgb.Booster()
        b.load_model(os.path.join(model_dir, f"modelo_b_{curso}.ubj"))
        models[f"booster_b_{curso}"] = b

        with open(os.path.join(model_dir, f"label_encoder_{curso}.json"), encoding="utf-8") as f:
            models[f"le_classes_{curso}"] = json.load(f)

    with open(os.path.join(model_dir, "preprocessor.json"), encoding="utf-8") as f:
        models["preprocessor"] = json.load(f)

    version_path = os.path.join(model_dir, "version.txt")
    models["version"] = open(version_path).read().strip() if os.path.exists(version_path) else "v1.0"

    logger.info("BistroTech models loaded — version %s", models["version"])
    return models


# ---------------------------------------------------------------------------
# SageMaker hook — parse request body
# ---------------------------------------------------------------------------
def input_fn(request_body: str, content_type: str = "application/json") -> dict:
    return json.loads(request_body)


# ---------------------------------------------------------------------------
# Feature engineering (pure numpy/pandas, no sklearn objects at runtime)
# ---------------------------------------------------------------------------
def _scale(value: float, s: dict) -> float:
    """Apply MinMaxScaler transform: (x - data_min) / data_range."""
    data_min = s["data_min_"][0]
    data_range = s["data_range_"][0]
    if data_range == 0:
        return 0.0
    scaled = (value - data_min) / data_range
    return float(np.clip(scaled, 0.0, 1.0))


def _build_features(contexto: dict, preprocessor: dict) -> pd.DataFrame:
    dia_semana  = contexto["dia_semana"]
    franja_hora = contexto["franja_horaria"]
    scalers     = preprocessor["scalers"]
    seg_means   = preprocessor["segment_means"]
    global_mean = preprocessor["global_mean_ticket"]

    rows = []
    for c in contexto["comensales"]:
        ticket = c.get("ticket_promedio_historico")
        if ticket is None:
            key = str((c["franja_etaria_persona"], franja_hora, c["motivo_visita"]))
            ticket = seg_means.get(key, global_mean)

        cant_acomp = c.get("cant_acompañantes", c.get("cant_acompanantes", 0))

        rows.append({
            "dia_semana":              dia_semana,
            "franja_horaria":          franja_hora,
            "franja_etaria_persona":   c["franja_etaria_persona"],
            "cant_acomp_raw":          float(cant_acomp),
            "viene_solo":              int(cant_acomp == 0),
            "es_repetidor":            int(bool(c["es_repetidor"])),
            "visitas_previas_raw":     float(c.get("visitas_previas", 0)),
            "ticket_raw":              float(ticket),
            "motivo_visita":           c["motivo_visita"],
            "restriccion_alimentaria": c.get("restriccion_alimentaria", "ninguna"),
            "orden_de_pedido_raw":     float(c.get("orden_de_pedido", 1)),
        })

    result = pd.DataFrame(index=range(len(rows)))

    dia_vals = [r["dia_semana"] for r in rows]
    result["dia_semana_sin"] = [np.sin(2 * np.pi * d / 7) for d in dia_vals]
    result["dia_semana_cos"] = [np.cos(2 * np.pi * d / 7) for d in dia_vals]

    for col, categories in CAT_FEATURES.items():
        for cat in sorted(categories):
            result[f"{col}_{cat}"] = [int(r[col] == cat) for r in rows]

    result["viene_solo"]   = [r["viene_solo"]   for r in rows]
    result["es_repetidor"] = [r["es_repetidor"] for r in rows]

    s_cant   = scalers["cant_acompañantes"]
    s_vis    = scalers["visitas_previas"]
    s_ticket = scalers["ticket_promedio_historico"]
    s_orden  = scalers["orden_de_pedido"]

    result["cant_acompañantes"] = [
        _scale(r["cant_acomp_raw"], s_cant) for r in rows
    ]
    result["visitas_previas"] = [
        _scale(float(np.log1p(r["visitas_previas_raw"])), s_vis) for r in rows
    ]
    result["ticket_promedio_historico"] = [
        _scale(r["ticket_raw"], s_ticket) for r in rows
    ]
    result["orden_de_pedido"] = [
        _scale(r["orden_de_pedido_raw"], s_orden) for r in rows
    ]

    expected = preprocessor["feature_names"]
    for col in expected:
        if col not in result.columns:
            result[col] = 0
    return result[expected].reset_index(drop=True)


# ---------------------------------------------------------------------------
# SageMaker hook — run prediction
# ---------------------------------------------------------------------------
def predict_fn(contexto: dict, models: dict) -> dict:
    t0           = time.time()
    preprocessor = models["preprocessor"]
    X_all        = _build_features(contexto, preprocessor)
    comensales   = contexto["comensales"]

    # --- Modelo A: waiter ranking ---
    booster_a     = models["booster_a"]
    feature_names = models["feature_names_a"]

    per_comensal_scores: list = []
    for i in range(len(comensales)):
        x_row = X_all.iloc[[i]].copy()
        scores_by_mozo: dict = {}
        for mozo_id in range(1, 9):
            x_m = x_row.copy()
            x_m["id_mozo"] = mozo_id
            x_m = x_m.reindex(columns=feature_names, fill_value=0)
            dm = xgb.DMatrix(x_m)
            score = float(booster_a.predict(dm)[0])
            scores_by_mozo[mozo_id] = float(np.clip(score, 0.0, 1.0))
        per_comensal_scores.append(scores_by_mozo)

    avg_scores = {
        mozo: float(np.mean([s[mozo] for s in per_comensal_scores]))
        for mozo in range(1, 9)
    }
    sorted_mozos = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
    mozos_recomendados = [
        {"id_mozo": m, "propina_rate_esperado": round(s, 4), "rank": r + 1}
        for r, (m, s) in enumerate(sorted_mozos)
    ]

    # --- Modelo B: menu recommendations ---
    recomendaciones: list = []
    for i, comensal in enumerate(comensales):
        restriccion = comensal.get("restriccion_alimentaria", "ninguna")
        x_row = X_all.iloc[[i]]
        menu: dict = {}

        for curso, dish_range in CURSO_DISH_RANGE.items():
            booster_b  = models[f"booster_b_{curso}"]
            le_classes = models[f"le_classes_{curso}"]  # list of dish ids

            dm    = xgb.DMatrix(x_row)
            proba = booster_b.predict(dm)[0]  # shape: (n_classes,) for multi:softprob

            # booster.predict for multi:softprob may return flat (n*c,) → reshape
            if proba.ndim == 1 and len(proba) == len(le_classes):
                pass  # already (n_classes,)
            elif proba.ndim == 1 and len(proba) > len(le_classes):
                proba = proba.reshape(-1, len(le_classes))[0]

            compatible = [d for d in dish_range if restriccion in DISH_RESTRICTIONS.get(d, [])]
            scored = []
            for dish_id in compatible:
                if dish_id in le_classes:
                    idx = le_classes.index(dish_id)
                    scored.append((dish_id, float(proba[idx])))

            scored.sort(key=lambda x: x[1], reverse=True)
            menu[curso] = [
                {"id_plato": int(did), "score": round(s, 4), "rank": rk + 1}
                for rk, (did, s) in enumerate(scored[:3])
            ]

        recomendaciones.append({
            "id_persona_en_mesa": comensal["id_persona_en_mesa"],
            **menu,
        })

    return {
        "id_mesa":                      contexto["id_mesa"],
        "mozos_recomendados":           mozos_recomendados,
        "recomendaciones_por_comensal": recomendaciones,
        "modelo_version":               models.get("version", "v1.0"),
        "latencia_ms":                  int((time.time() - t0) * 1000),
    }


# ---------------------------------------------------------------------------
# SageMaker hook — serialize response
# ---------------------------------------------------------------------------
def output_fn(prediction: dict, accept: str = "application/json") -> str:
    return json.dumps(prediction, ensure_ascii=False)
