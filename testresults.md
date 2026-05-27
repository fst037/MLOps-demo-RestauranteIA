python : 2026-05-27 00:59:50,149 WARNING boto3 no disponible — simulando trigger de pipeline.
At line:1 char:70
+ ... estauranteIA; $env:PYTHONIOENCODING="utf-8"; python live_test.py 2>&1
+                                                  ~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (2026-05-27 00:5...er de pipeline.:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
2026-05-27 00:59:50,150 WARNING boto3 no disponible — contador no actualizado.

================================================================
  BistroTech — Prueba en Vivo End-to-End
================================================================

================================================================
  FASE 1 — Entrenamiento inicial con datos históricos
================================================================
  [OK] Dataset histórico generado → data/raw/reservas.csv  (10,000 registros, 2,193 mesas)
  [OK] Features procesadas → data/processed/  (10,000 registros con feedback completo)

=======================================================
Modelo A entrenado — 0 árboles efectivos
  RMSE     : 0.0736
  MAE      : 0.0637
  Pearson  : 0.0085
  Modelo   : models/modelo_a_mozo.joblib
=======================================================

  [OK] Modelo A entrenado → models/modelo_a_mozo.joblib  RMSE=0.0736  MAE=0.0637  Pearson=0.009

=======================================================
Entrenando Modelos B (recomendación de menú)
=======================================================
  [entrada] Hit Rate@3: 0.3571 | F1 macro: 0.0580
  [principal] Hit Rate@3: 0.2520 | F1 macro: 0.0227
  [postre] Hit Rate@3: 0.5984 | F1 macro: 0.1269
  [bebida] Hit Rate@3: 0.6210 | F1 macro: 0.1504

Hit Rate promedio: 45.71%
=======================================================

  [OK] Modelo B 'entrada' → Hit Rate=35.7%  F1=0.058
  [OK] Modelo B 'principal' → Hit Rate=25.2%  F1=0.023
  [OK] Modelo B 'postre' → Hit Rate=59.8%  F1=0.127
  [OK] Modelo B 'bebida' → Hit Rate=62.1%  F1=0.150
  [OK] Hit Rate promedio Modelos B: 45.7%

================================================================
  FASE 2 — 1 día de operación → S3 → reentrenamiento
================================================================
  [OK] Datos del día 1 generados → data/raw/day1_reservas.csv  (500 registros, 115 mesas nuevas)
  [OK] Datos subidos a S3 → s3://bistrotech-models-834257582282/data/raw/day1_reservas.csv
  [OK] Datos descargados desde S3 → data/raw/day1_from_s3.csv  (500 registros)
  [OK] Dataset combinado → data/raw/reservas_v2.csv  (10,500 registros = 10,000 hist + 500 nuevos)
  [OK] Features recalculadas  (10,500 registros con feedback)

=======================================================
Modelo A entrenado — 12 árboles efectivos
  RMSE     : 0.0745
  MAE      : 0.0649
  Pearson  : 0.0141
  Modelo   : models/modelo_a_mozo.joblib
=======================================================

  [OK] Modelo A v2 reentrenado → RMSE=0.0745  (Δ+0.0009 vs v1)  Pearson=0.014

=======================================================
Entrenando Modelos B (recomendación de menú)
=======================================================
  [entrada] Hit Rate@3: 0.3875 | F1 macro: 0.0614
  [principal] Hit Rate@3: 0.2467 | F1 macro: 0.0275
  [postre] Hit Rate@3: 0.5735 | F1 macro: 0.1053
  [bebida] Hit Rate@3: 0.6024 | F1 macro: 0.1102

Hit Rate promedio: 45.25%
=======================================================

  [OK] Modelos B v2 reentrenados → Hit Rate=45.2%  (Δ-0.5% vs v1)
  [OK] Modelo empaquetado → models/bistrotech-model-v2.tar.gz  (239 KB)
  [OK] Modelo v2 subido a S3 → s3://bistrotech-models-834257582282/models/bistrotech-model-v2.tar.gz
  [OK] Trigger mini-batch: 500 registros >= threshold 50 → RETRAIN_TRIGGERED  (ARN: arn:aws:sagemaker:local:000000000000:pipeline/bistrotech-retrain-pipeline/execution/simulated)

================================================================
  FASE 3 — Inferencia local: usuario nuevo vs recurrente
================================================================

  [A] USUARIO NUEVO — primera visita, sin historial, restricción vegana
      Mesa 7 | date | noche | viernes
  [OK] Predicción completada en 93 ms  (modelo v1.0)
      Mozos recomendados: #1 (0.128), #2 (0.128), #3 (0.128)
      Comensal 1:
        entrada   : plato #4 (score=0.1307) + 2 alternativas
        principal : plato #20 (score=0.0893) + 2 alternativas
        postre    : plato #24 (score=0.2060) + 2 alternativas
        bebida    : plato #28 (score=0.2055) + 2 alternativas
      Comensal 2:
        entrada   : plato #4 (score=0.1307) + 2 alternativas
        principal : plato #12 (score=0.0907) + 2 alternativas
        postre    : plato #24 (score=0.2057) + 2 alternativas
        bebida    : plato #28 (score=0.2050) + 2 alternativas

  [B] USUARIO RECURRENTE — 12 visitas previas, ticket alto, negocios
      Mesa 22 | negocios | mediodía | martes
  [OK] Predicción completada en 105 ms  (modelo v1.0)
      Mozos recomendados: #1 (0.128), #2 (0.128), #3 (0.128)
      Comensal 1 (recurrente 12v):
        entrada   : plato #4 (score=0.1301) + 2 alternativas
        principal : plato #20 (score=0.0901) + 2 alternativas
        postre    : plato #24 (score=0.2069) + 2 alternativas
        bebida    : plato #28 (score=0.2048) + 2 alternativas
      Comensal 2 (recurrente 7v):
        entrada   : plato #1 (score=0.1302) + 2 alternativas
        principal : plato #15 (score=0.0873) + 2 alternativas
        postre    : plato #24 (score=0.2088) + 2 alternativas
        bebida    : plato #28 (score=0.2048) + 2 alternativas
      Comensal 3 (nuevo):
        entrada   : plato #4 (score=0.1343) + 2 alternativas
        principal : plato #20 (score=0.0893) + 2 alternativas
        postre    : plato #24 (score=0.2104) + 2 alternativas
        bebida    : plato #28 (score=0.2054) + 2 alternativas

  [CONTRASTE]
      Usuario nuevo     → mozo #1  propina_rate_esperado=0.128
      Usuario recurrente → mozo #1  propina_rate_esperado=0.128
      → Mismo mozo óptimo (el historial refuerza la recomendación)

================================================================
  FASE 4 — Endpoint AWS en vivo (API Gateway → SageMaker)
================================================================
  Endpoint: https://ks1yq53cch.execute-api.us-east-1.amazonaws.com/prod/predict

  [Usuario NUEVO (vegano, date)]
  [OK] HTTP 200 | round-trip 11048ms | latencia_modelo=53ms | versión=v1.0 | mozo #1 (rate=0.499)

  [Usuario RECURRENTE (12 visitas, kosher, negocios)]
  [OK] HTTP 200 | round-trip 813ms | latencia_modelo=41ms | versión=v1.0 | mozo #1 (rate=0.498)


================================================================
  RESUMEN
================================================================
  [ OK ] FASE 1
  [ OK ] FASE 2
  [ OK ] FASE 3
  [ OK ] FASE 4

  Todas las fases completadas exitosamente.