import json
import ssl
import time
import urllib.request

API_URL = "https://ks1yq53cch.execute-api.us-east-1.amazonaws.com/prod/predict"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

casos = [
    ("Usuario NUEVO (date, sin historial)", {
        "id_mesa": 7, "dia_semana": 4, "franja_horaria": "noche",
        "comensales": [{
            "id_persona_en_mesa": 1, "franja_etaria_persona": "adulto",
            "cant_acompanantes": 1, "motivo_visita": "date",
            "es_repetidor": False, "visitas_previas": 0,
            "ticket_promedio_historico": None, "orden_de_pedido": 1,
        }],
    }),
    ("Usuario RECURRENTE (negocios, 12 visitas)", {
        "id_mesa": 22, "dia_semana": 1, "franja_horaria": "mediodia",
        "comensales": [{
            "id_persona_en_mesa": 1, "franja_etaria_persona": "adulto",
            "cant_acompanantes": 2, "motivo_visita": "negocios",
            "es_repetidor": True, "visitas_previas": 12,
            "ticket_promedio_historico": 4200.0, "orden_de_pedido": 1,
        }],
    }),
]

for label, payload in casos:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            elapsed = int((time.time() - t0) * 1000)
            data = json.loads(resp.read())
            top = data["mozos_recomendados"][0]
            version = data["modelo_version"]
            latencia = data["latencia_ms"]
            print(f"[OK] {label}")
            print(f"     HTTP 200 | round-trip {elapsed}ms | latencia_modelo={latencia}ms | version={version}")
            print(f"     Mozo #{top['id_mozo']} (propina_rate={top['propina_rate_esperado']:.3f})")
            rec = data["recomendaciones_por_comensal"][0]
            for curso in ["entrada", "principal", "postre", "bebida"]:
                platos = rec.get(curso, [])
                if platos:
                    p = platos[0]
                    print(f"     {curso:10s}: plato #{p['id_plato']} (score={p['score']:.4f})")
    except Exception as e:
        print(f"[!!] {label}: {e}")
    print()
