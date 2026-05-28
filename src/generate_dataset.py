"""
Simulador de dataset para BistroTech.
Genera registros con señal real: afinidad mozo-cliente y preferencias de platos por segmento.
"""
import os
import logging
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROP_MAP = {"nada": 0.0, "poco": 0.2, "mitad": 0.5, "mayoria": 0.8, "todo": 1.0}

# ---------------------------------------------------------------------------
# Waiter affinity profiles
# Each waiter excels with a specific (motivo, franja_etaria, franja_horaria).
# P(like_mozo) = 0.28 base + 0.30 if motivo matches + 0.22 if etaria matches + 0.14 if horaria matches
# Perfect match → 0.94; no match → 0.28
# ---------------------------------------------------------------------------
MOZO_PROFILES = {
    1: {"motivo": "negocios",   "etaria": "adulto",  "horaria": "mediodia"},
    2: {"motivo": "date",       "etaria": "joven",   "horaria": "noche"},
    3: {"motivo": "casual",     "etaria": "adulto",  "horaria": "tarde"},
    4: {"motivo": "cumpleaños", "etaria": "joven",   "horaria": "noche"},
    5: {"motivo": "turista",    "etaria": "senior",  "horaria": "mediodia"},
    6: {"motivo": "negocios",   "etaria": "senior",  "horaria": "mediodia"},
    7: {"motivo": "casual",     "etaria": "joven",   "horaria": "noche"},
    8: {"motivo": "date",       "etaria": "adulto",  "horaria": "tarde"},
}
# Affinity score → propina_rate is continuous (no Bernoulli noise layer)
# Perfect match → score=1.0; no match → score=0.05 (20× spread)
_MOZO_BASE    = 0.05
_MOZO_MOTIVO  = 0.45
_MOZO_ETARIA  = 0.32
_MOZO_HORARIA = 0.22

# ---------------------------------------------------------------------------
# Dish preference weights — top-3 dishes get 90-97% of probability mass.
# Segments with no restriccion use etaria/motivo (both in feature set).
# Index 0 = lowest dish ID in each range.
# entrada: IDs 1-8  | principal: IDs 9-20  | postre: IDs 21-25  | bebida: IDs 26-30
# ---------------------------------------------------------------------------
_W_ENTRADA = {
    # restriccion-based (data generation only — not model features)
    "vegano":      [0.50, 0.35, 0.10, 0.02, 0.01, 0.01, 0.01, 0.00],
    "vegetariano": [0.32, 0.30, 0.22, 0.10, 0.04, 0.01, 0.01, 0.00],
    "celiaco":     [0.01, 0.01, 0.02, 0.42, 0.45, 0.06, 0.02, 0.01],
    "kosher":      [0.00, 0.01, 0.01, 0.02, 0.04, 0.30, 0.38, 0.24],
    # etaria-based: non-overlapping clusters — maximally learnable
    "joven":       [0.50, 0.35, 0.12, 0.02, 0.01, 0.00, 0.00, 0.00],
    "adulto":      [0.01, 0.01, 0.02, 0.04, 0.06, 0.42, 0.32, 0.12],
    "senior":      [0.00, 0.00, 0.01, 0.01, 0.02, 0.10, 0.38, 0.48],
}

_W_PRINCIPAL = {
    # restriccion-based (data generation only)
    "vegano":      [0.42, 0.35, 0.16, 0.04, 0.01, 0.01, 0.01, 0.00, 0.00, 0.00, 0.00, 0.00],
    "vegetariano": [0.25, 0.22, 0.20, 0.16, 0.10, 0.04, 0.02, 0.01, 0.00, 0.00, 0.00, 0.00],
    "celiaco":     [0.00, 0.01, 0.01, 0.02, 0.02, 0.03, 0.04, 0.05, 0.28, 0.30, 0.16, 0.08],
    "kosher":      [0.00, 0.00, 0.01, 0.01, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.35, 0.32],
    # etaria/motivo-based — non-overlapping clusters of 3 dishes each
    "negocios":    [0.00, 0.00, 0.00, 0.00, 0.01, 0.01, 0.01, 0.02, 0.04, 0.08, 0.42, 0.41],
    "joven":       [0.45, 0.35, 0.14, 0.03, 0.01, 0.01, 0.01, 0.00, 0.00, 0.00, 0.00, 0.00],
    "adulto":      [0.01, 0.01, 0.02, 0.04, 0.38, 0.40, 0.10, 0.02, 0.01, 0.01, 0.00, 0.00],
    "senior":      [0.00, 0.00, 0.00, 0.01, 0.01, 0.01, 0.02, 0.04, 0.10, 0.38, 0.38, 0.05],
}

_W_POSTRE = {
    # restriccion-based (data generation only)
    "vegano":      [0.55, 0.35, 0.07, 0.02, 0.01],
    "vegetariano": [0.35, 0.32, 0.20, 0.10, 0.03],
    "celiaco":     [0.02, 0.03, 0.72, 0.18, 0.05],
    "kosher":      [0.02, 0.03, 0.05, 0.38, 0.52],
    # etaria-based: completely opposite preferences
    "joven":       [0.01, 0.02, 0.07, 0.42, 0.48],
    "adulto":      [0.08, 0.12, 0.38, 0.28, 0.14],
    "senior":      [0.52, 0.35, 0.10, 0.02, 0.01],
}

_W_BEBIDA = {
    # motivo-based: near-deterministic — primary learnable signal
    "negocios":      [0.00, 0.00, 0.02, 0.10, 0.88],
    "date":          [0.01, 0.01, 0.06, 0.78, 0.14],
    "cumpleaños":    [0.02, 0.04, 0.86, 0.05, 0.03],
    "turista":       [0.62, 0.30, 0.05, 0.02, 0.01],
    "casual_joven":  [0.75, 0.18, 0.05, 0.01, 0.01],
    "casual_adulto": [0.01, 0.03, 0.06, 0.22, 0.68],
    "casual_senior": [0.01, 0.72, 0.03, 0.14, 0.10],
}


def _mozo_affinity(id_mozo: int, motivo: str, etaria: str, horaria: str) -> float:
    """Continuous affinity score in [0.05, 1.04] → capped at 1.0."""
    p = MOZO_PROFILES[id_mozo]
    score = _MOZO_BASE
    if motivo  == p["motivo"]:  score += _MOZO_MOTIVO
    if etaria  == p["etaria"]:  score += _MOZO_ETARIA
    if horaria == p["horaria"]: score += _MOZO_HORARIA
    return min(score, 1.0)


def _choose(ids: list, weights: list) -> int:
    w = np.array(weights, dtype=float)
    w /= w.sum()
    return int(np.random.choice(ids, p=w))


def _entrada_key(restriccion: str, etaria: str) -> str:
    return restriccion if restriccion != "ninguna" else etaria


def _principal_key(restriccion: str, motivo: str, etaria: str) -> str:
    if restriccion != "ninguna":
        return restriccion
    if motivo == "negocios":
        return "negocios"
    return etaria


def _postre_key(restriccion: str, etaria: str) -> str:
    return restriccion if restriccion != "ninguna" else etaria


def _bebida_key(motivo: str, etaria: str) -> str:
    if motivo in ("negocios", "date", "cumpleaños", "turista"):
        return motivo
    return f"casual_{etaria}"


def _gen_proporcion(like: bool) -> str:
    if like:
        return np.random.choice(
            ["nada", "poco", "mitad", "mayoria", "todo"],
            p=[0.60, 0.30, 0.07, 0.02, 0.01],
        )
    return np.random.choice(
        ["nada", "poco", "mitad", "mayoria", "todo"],
        p=[0.00, 0.00, 0.40, 0.40, 0.20],
    )


def _calc_score(like, proporcion: str, tiempo_normalizado: float):
    if like is None or proporcion is None:
        return None
    prop_val = PROP_MAP[proporcion]
    return round(0.5 * (1 - prop_val) + 0.3 * float(like) + 0.2 * tiempo_normalizado, 4)


def generate(n_records: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """
    Genera el dataset simulado con señal real:
      - propina_rate determinado por afinidad mozo × segmento de cliente
      - elección de platos determinada por restricción alimentaria + motivo + franja etaria
    """
    np.random.seed(seed)
    records = []
    id_registro = 1
    id_mesa = 1
    id_cliente = 1
    start_date = pd.Timestamp("2024-01-01")

    ENTRADAS   = list(range(1, 9))
    PRINCIPALES = list(range(9, 21))
    POSTRES    = list(range(21, 26))
    BEBIDAS    = list(range(26, 31))

    while len(records) < n_records:
        mesa_size = int(np.random.randint(1, 9))

        offset_days = int(np.random.randint(0, 365))
        fecha_base = start_date + pd.Timedelta(days=offset_days)
        dia_semana = fecha_base.dayofweek

        franja_horaria = np.random.choice(
            ["mediodia", "tarde", "noche"], p=[0.40, 0.15, 0.45]
        )
        hora_inicio = {"mediodia": 12, "tarde": 16, "noche": 20}[franja_horaria]
        hora_base = fecha_base + pd.Timedelta(
            hours=hora_inicio, minutes=int(np.random.randint(0, 60))
        )

        id_mozo_mesa = int(np.random.randint(1, 9))

        for persona in range(1, mesa_size + 1):
            if len(records) >= n_records:
                break

            franja_etaria = np.random.choice(
                ["joven", "adulto", "senior"], p=[0.40, 0.45, 0.15]
            )

            if franja_horaria == "mediodia":
                motivo = np.random.choice(
                    ["negocios", "casual", "turista"], p=[0.50, 0.40, 0.10]
                )
            elif franja_horaria == "tarde":
                motivo = np.random.choice(
                    ["casual", "date", "turista", "cumpleaños"], p=[0.45, 0.25, 0.20, 0.10]
                )
            else:
                motivo = np.random.choice(
                    ["date", "cumpleaños", "casual", "turista"], p=[0.30, 0.25, 0.35, 0.10]
                )

            restriccion = np.random.choice(
                ["ninguna", "vegetariano", "vegano", "celiaco", "kosher"],
                p=[0.70, 0.15, 0.08, 0.05, 0.02],
            )

            es_repetidor = bool(np.random.random() < 0.60)
            if es_repetidor:
                visitas_previas = int(np.random.randint(1, 21))
                ticket_promedio_historico = round(float(np.random.uniform(800, 8000)), 2)
            else:
                visitas_previas = 0
                ticket_promedio_historico = (
                    None
                    if np.random.random() < 0.30
                    else round(float(np.random.uniform(500, 3000)), 2)
                )

            cliente_id = id_cliente if np.random.random() < 0.80 else None

            # Dish choices: segment-driven weighted sampling
            has_entrada = np.random.random() >= 0.20
            has_postre  = np.random.random() >= 0.30

            id_entrada = (
                _choose(ENTRADAS, _W_ENTRADA[_entrada_key(restriccion, franja_etaria)])
                if has_entrada else None
            )
            id_principal = _choose(
                PRINCIPALES,
                _W_PRINCIPAL[_principal_key(restriccion, motivo, franja_etaria)],
            )
            id_postre = (
                _choose(POSTRES, _W_POSTRE[_postre_key(restriccion, franja_etaria)])
                if has_postre else None
            )
            id_bebida = _choose(BEBIDAS, _W_BEBIDA[_bebida_key(motivo, franja_etaria)])

            # propina_rate: continuous affinity → rate (no Bernoulli noise layer)
            affinity = _mozo_affinity(id_mozo_mesa, motivo, franja_etaria, franja_horaria)
            like_mozo = bool(np.random.random() < affinity)
            base_propina = 0.02 + 0.40 * affinity
            propina_rate = round(
                float(np.clip(base_propina + np.random.uniform(-0.015, 0.015), 0.0, 0.50)), 4
            )

            like_entrada   = bool(np.random.random() < 0.70) if id_entrada is not None else None
            like_principal = bool(np.random.random() < 0.70)
            like_postre    = bool(np.random.random() < 0.70) if id_postre is not None else None
            like_bebida    = bool(np.random.random() < 0.70)

            prop_entrada   = _gen_proporcion(like_entrada)  if id_entrada is not None else None
            prop_principal = _gen_proporcion(like_principal)
            prop_postre    = _gen_proporcion(like_postre)   if id_postre is not None else None

            hora_entrega = hora_base + pd.Timedelta(minutes=int(np.random.randint(10, 35)))
            tiempo_consumo_min = int(np.random.randint(15, 46))
            hora_retiro = hora_entrega + pd.Timedelta(minutes=tiempo_consumo_min)
            tiempo_normalizado = round(1.0 - tiempo_consumo_min / 45.0, 4)

            total_cuenta = round(float(np.random.uniform(2000, 8000)), 2)
            monto_propina = round(propina_rate * total_cuenta, 2)

            records.append(
                {
                    "id_registro": id_registro,
                    "id_mesa": id_mesa,
                    "id_cliente": cliente_id,
                    "id_persona_en_mesa": persona,
                    "fecha_hora": hora_base,
                    "dia_semana": dia_semana,
                    "franja_horaria": franja_horaria,
                    "franja_etaria_persona": franja_etaria,
                    "cant_acompañantes": mesa_size - 1,
                    "viene_solo": bool(mesa_size == 1),
                    "es_repetidor": es_repetidor,
                    "visitas_previas": visitas_previas,
                    "ticket_promedio_historico": ticket_promedio_historico,
                    "motivo_visita": motivo,
                    "restriccion_alimentaria": restriccion,
                    "orden_de_pedido": persona,
                    "id_mozo": id_mozo_mesa,
                    "id_entrada": id_entrada,
                    "id_principal": id_principal,
                    "id_postre": id_postre,
                    "id_bebida": id_bebida,
                    "hora_entrega_plato": hora_entrega,
                    "hora_retiro_plato": hora_retiro,
                    "proporcion_dejada_entrada": prop_entrada,
                    "proporcion_dejada_principal": prop_principal,
                    "proporcion_dejada_postre": prop_postre,
                    "monto_propina": monto_propina,
                    "propina_rate": propina_rate,
                    "score_satisfaccion_entrada": _calc_score(
                        like_entrada, prop_entrada, tiempo_normalizado
                    ),
                    "score_satisfaccion_principal": _calc_score(
                        like_principal, prop_principal, tiempo_normalizado
                    ),
                    "score_satisfaccion_postre": _calc_score(
                        like_postre, prop_postre, tiempo_normalizado
                    ),
                    "like_mozo": like_mozo,
                    "like_entrada": like_entrada,
                    "like_principal": like_principal,
                    "like_postre": like_postre,
                    "like_bebida": like_bebida,
                }
            )

            id_registro += 1
            id_cliente += 1

        id_mesa += 1

    df = pd.DataFrame(records[:n_records])
    logger.info(
        "Dataset generado: %d registros, %d mesas, seed=%d",
        len(df), df["id_mesa"].nunique(), seed,
    )
    return df


def print_stats(df: pd.DataFrame) -> None:
    print(f"\n{'='*55}")
    print(f"Total registros       : {len(df)}")
    print(f"Mesas únicas          : {df['id_mesa'].nunique()}")
    print(f"Clientes únicos (id)  : {df['id_cliente'].nunique()}")
    print("\nPropina rate promedio por mozo:")
    by_mozo = df.groupby("id_mozo")["propina_rate"].mean().round(4)
    for mozo, rate in by_mozo.items():
        print(f"  Mozo {mozo}: {rate:.4f}")
    print("\nDistribución restricción alimentaria:")
    dist = df["restriccion_alimentaria"].value_counts(normalize=True).round(3)
    for k, v in dist.items():
        print(f"  {k:<14}: {v:.1%}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    import shutil
    os.makedirs("data/raw", exist_ok=True)

    for seed, label in [(42, "A"), (137, "B")]:
        df = generate(10_000, seed=seed)
        path = f"data/raw/reservas_{label}.csv"
        df.to_csv(path, index=False)
        logger.info("Guardado en %s", path)
        print_stats(df)

    # backward compat: reservas.csv = dataset A
    shutil.copy("data/raw/reservas_A.csv", "data/raw/reservas.csv")
    logger.info("reservas.csv actualizado (= reservas_A.csv)")
