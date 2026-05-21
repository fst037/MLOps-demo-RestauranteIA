# BistroTech — Sistema de Recomendación Gastronómica con MLOps

## Descripción
Sistema de recomendación en tiempo real para restaurantes que sugiere el mozo
más afín y los platos más probables para cada comensal, basado en su perfil
individual y contexto de visita. El sistema aprende continuamente a partir del
feedback implícito (comida dejada, tiempo de consumo) y explícito (propina,
likes) registrado durante el servicio.

## Arquitectura General

```
Reserva/POS → API Gateway → Lambda → SageMaker Endpoint → Recomendación
                                   ↓
                            Kinesis Streams (eventos)
                                   ↓
                          SageMaker Feature Store
                                   ↓
                    Mini-batch trigger (cada 50 registros completos)
                                   ↓
                         SageMaker Pipelines (retrain)
                                   ↓
                    Model Registry → Evaluación automática
                                   ↓
                    Si mejora métricas → Deploy full-auto
                                   ↓
                         CloudWatch (monitoreo + alertas)
```

## Modelos

### Modelo A — Afinidad de Mozo
- **Algoritmo:** XGBoost Regressor
- **Target:** `propina_rate` esperado por mozo (valor continuo 0-1)
- **Predicción en mesa:** promedio ponderado de scores individuales de cada comensal
- **Métricas:** RMSE, MAE, Pearson Correlation

### Modelos B — Recomendación de Menú (4 modelos independientes)
- **Algoritmo:** XGBoost Classifier con softmax
- **Targets:** `id_entrada`, `id_principal`, `id_postre`, `id_bebida`
- **Métricas:** Hit Rate @ 3, F1-Score macro

## Modelo de Datos

### Tabla: `registros` (unidad = 1 persona en 1 visita)

| Campo | Tipo | Descripción |
|---|---|---|
| `id_registro` | INT PK | Identificador único |
| `id_mesa` | INT FK | Agrupa comensales de la misma visita |
| `id_cliente` | INT FK | Nullable (walk-ins sin identificar) |
| `id_persona_en_mesa` | INT | Posición en la mesa (1, 2, 3...) |
| `fecha_hora` | DATETIME | Timestamp de la reserva |
| `dia_semana` | INT (0-6) | Lunes=0, Domingo=6 |
| `franja_horaria` | ENUM | mediodia / tarde / noche |
| `franja_etaria_persona` | ENUM | joven / adulto / senior |
| `cant_acompañantes` | INT | 0 = viene solo |
| `viene_solo` | BOOL | Derivado de cant_acompañantes == 0 |
| `es_repetidor` | BOOL | Tuvo visitas previas registradas |
| `visitas_previas` | INT | 0 si cliente nuevo |
| `ticket_promedio_historico` | FLOAT | Nullable, imputado por segmento si null |
| `motivo_visita` | ENUM | cumpleaños / negocios / casual / date / turista |
| `restriccion_alimentaria` | ENUM | vegano / vegetariano / celiaco / ninguna |
| `orden_de_pedido` | INT | Orden en que pidió dentro de la mesa |
| `id_mozo` | INT FK | Mozo asignado |
| `id_entrada` | INT FK | Nullable |
| `id_principal` | INT FK | Nullable |
| `id_postre` | INT FK | Nullable |
| `id_bebida` | INT FK | Nullable |
| `hora_entrega_plato` | DATETIME | Registrado por POS |
| `hora_retiro_plato` | DATETIME | Registrado por mozo |
| `proporcion_dejada_entrada` | ENUM | nada / poco / mitad / mayoria / todo |
| `proporcion_dejada_principal` | ENUM | nada / poco / mitad / mayoria / todo |
| `proporcion_dejada_postre` | ENUM | nada / poco / mitad / mayoria / todo |
| `monto_propina` | FLOAT | Del cierre de cuenta |
| `propina_rate` | FLOAT | monto_propina / total_cuenta |
| `score_satisfaccion_entrada` | FLOAT | Calculado: tiempo + proporcion + like |
| `score_satisfaccion_principal` | FLOAT | Calculado |
| `score_satisfaccion_postre` | FLOAT | Calculado |
| `like_mozo` | BOOL | Feedback explícito opcional |
| `like_entrada` | BOOL | Feedback explícito opcional |
| `like_principal` | BOOL | Feedback explícito opcional |
| `like_postre` | BOOL | Feedback explícito opcional |
| `like_bebida` | BOOL | Feedback explícito opcional |

### Tabla: `clientes_historico` (perfil acumulado)

| Campo | Tipo | Descripción |
|---|---|---|
| `id_cliente` | INT PK | |
| `visitas_totales` | INT | |
| `ticket_promedio` | FLOAT | |
| `restriccion_detectada` | ENUM | Inferida del comportamiento |
| `motivo_frecuente` | ENUM | Motivo de visita más común |
| `franja_horaria_frecuente` | ENUM | |
| `like_rate_promedio` | FLOAT | Satisfacción histórica promedio |
| `platos_frecuentes` | JSON | Array de id_plato más pedidos |

### Tabla: `segmentos_referencia` (cold start)

| Campo | Tipo | Descripción |
|---|---|---|
| `franja_etaria` | ENUM | Clave de segmento |
| `franja_horaria` | ENUM | Clave de segmento |
| `motivo_visita` | ENUM | Clave de segmento |
| `ticket_promedio_segmento` | FLOAT | Media del segmento |
| `platos_populares_segmento` | JSON | Top platos del segmento |
| `propina_rate_segmento` | FLOAT | Media del segmento |

## Feature Engineering

### Transformaciones aplicadas

| Feature | Transformación | Justificación |
|---|---|---|
| `dia_semana` | Seno/Coseno cíclico | Domingo cercano a Lunes |
| `franja_horaria` | One-Hot Encoding | Sin orden inherente |
| `franja_etaria_persona` | One-Hot Encoding | Sin orden inherente |
| `motivo_visita` | One-Hot Encoding | Sin orden inherente |
| `restriccion_alimentaria` | One-Hot Encoding | Sin orden inherente |
| `cant_acompañantes` | MinMaxScaler | Normalización |
| `ticket_promedio_historico` | Imputación por segmento + MinMaxScaler | Cold start |
| `visitas_previas` | Log1p + MinMaxScaler | Distribución sesgada |
| `orden_de_pedido` | MinMaxScaler | |

### Data Leakage — Separación train/serve

**Disponibles en inferencia (antes de servir):**
franja_etaria, cant_acompañantes, viene_solo, es_repetidor, visitas_previas,
ticket_promedio_historico, motivo_visita, restriccion_alimentaria,
dia_semana, franja_horaria, orden_de_pedido

**Solo disponibles post-servicio (targets de entrenamiento, NUNCA features de inferencia):**
hora_retiro_plato, proporcion_dejada_*, monto_propina, propina_rate,
score_satisfaccion_*, like_*

## Pipeline MLOps

### Ciclo de vida de un registro

```
T+0min    Reserva entra → Feature Store → Predicción → Guardada en S3
T+90min   Mozo retira platos → Evento feedback → Kinesis → Feature Store
T+120min  Cliente paga → Propina registrada → Evento cierre → Kinesis
T+Batch   Lambda verifica: ¿50 registros completos nuevos?
            SÍ → Dispara SageMaker Pipeline
            NO → Espera próximo evento
T+Retrain Pipeline: join predicciones + feedback → calcula scores
            → entrena nuevo modelo → evalúa vs producción
            → si mejora >5% → deploy full-auto → nuevo endpoint activo
            → si no mejora → descarta → CloudWatch log
```

### Estrategia de reentrenamiento: Mini-batch Triggered
- **Trigger:** acumulación de 50 registros completos (con feedback)
- **Algoritmo:** XGBoost (no soporta online learning nativo)
- **Justificación:** balance óptimo entre frescura del modelo y costo computacional
- **Deploy:** full-automático si métricas mejoran >5%

### Umbral de mejora para deploy automático
| Modelo | Métrica | Umbral mínimo de mejora |
|---|---|---|
| Modelo A (mozo) | RMSE propina_rate | -5% (menor es mejor) |
| Modelo B entrada | Hit Rate @ 3 | +5% |
| Modelo B principal | Hit Rate @ 3 | +5% |
| Modelo B postre | Hit Rate @ 3 | +5% |
| Modelo B bebida | Hit Rate @ 3 | +5% |

## Estructura del Proyecto

```
bistrotech/
├── README.md
├── requirements.txt
├── run_pipeline.py                  # Orquestador local completo
├── data/
│   ├── raw/                         # Dataset crudo simulado
│   └── processed/                   # Features procesadas
├── models/                          # Modelos serializados localmente
├── src/
│   ├── __init__.py
│   ├── generate_dataset.py          # Simulador de datos
│   ├── feature_engineering.py       # Transformaciones
│   ├── feature_store.py             # Interfaz con SageMaker Feature Store
│   ├── train_modelo_a.py            # XGBoost mozo
│   ├── train_modelo_b.py            # XGBoost menú x4
│   ├── evaluate.py                  # Métricas y comparación de versiones
│   └── inference.py                 # predict() functions
├── serve/
│   ├── inference.py                 # Entry point SageMaker (model_fn etc)
│   └── requirements.txt
├── pipelines/
│   ├── retrain_pipeline.py          # SageMaker Pipeline definition
│   ├── trigger_lambda.py            # Lambda mini-batch trigger
│   └── deploy_lambda.py             # Lambda deploy full-auto
├── monitoring/
│   ├── cloudwatch_config.json       # Alarmas y dashboards
│   └── drift_detector.py            # Detección de model drift
├── infrastructure/
│   ├── deploy_sagemaker.py          # Deploy inicial
│   ├── package_model.py             # Empaqueta y sube a S3
│   └── setup_kinesis.py             # Configura streams
└── tests/
    ├── test_features.py
    ├── test_inference.py
    └── test_endpoint.py
```

## Componentes AWS Utilizados

| Servicio | Uso |
|---|---|
| S3 | Data lake, modelos serializados, logs |
| SageMaker Feature Store | Fuente única de features (online + offline) |
| SageMaker Training Jobs | Entrenamiento de modelos |
| SageMaker Pipelines | Orquestación del retrain |
| SageMaker Model Registry | Versionado de modelos |
| SageMaker Endpoints | Inferencia en tiempo real |
| Kinesis Data Streams | Ingesta de eventos en tiempo real |
| Lambda | Trigger mini-batch, deploy automático |
| API Gateway | Entry point externo |
| CloudWatch | Monitoreo, alertas, drift detection |

## Cómo ejecutar localmente

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Correr pipeline completo (simula todo el ciclo)
python run_pipeline.py

# 3. Probar inferencia
python src/inference.py

# 4. Deploy en AWS (requiere credenciales configuradas)
export SAGEMAKER_ROLE_ARN="arn:aws:iam::TU_CUENTA:role/SageMakerRole"
python infrastructure/deploy_sagemaker.py
```

## Formato de la API

### Input
```json
{
  "id_mesa": 42,
  "comensales": [
    {
      "id_persona_en_mesa": 1,
      "franja_etaria_persona": "adulto",
      "cant_acompañantes": 3,
      "motivo_visita": "negocios",
      "restriccion_alimentaria": "ninguna",
      "es_repetidor": true,
      "visitas_previas": 5,
      "ticket_promedio_historico": 3200.0,
      "orden_de_pedido": 1
    }
  ],
  "dia_semana": 1,
  "franja_horaria": "mediodia"
}
```

### Output
```json
{
  "id_mesa": 42,
  "mozos_recomendados": [
    {"id_mozo": 3, "propina_rate_esperado": 0.18, "rank": 1},
    {"id_mozo": 7, "propina_rate_esperado": 0.15, "rank": 2},
    {"id_mozo": 1, "propina_rate_esperado": 0.12, "rank": 3}
  ],
  "recomendaciones_por_comensal": [
    {
      "id_persona_en_mesa": 1,
      "entrada": [{"id_plato": 5, "score": 0.91, "rank": 1}],
      "principal": [{"id_plato": 12, "score": 0.87, "rank": 1}],
      "postre": [{"id_plato": 23, "score": 0.74, "rank": 1}],
      "bebida": [{"id_plato": 31, "score": 0.95, "rank": 1}]
    }
  ],
  "modelo_version": "v1.4",
  "latencia_ms": 43
}
```

## Variables de Entorno Requeridas

```bash
SAGEMAKER_ROLE_ARN=arn:aws:iam::CUENTA:role/SageMakerRole
S3_BUCKET=bistrotech-models-CUENTA
KINESIS_STREAM_EVENTOS=bistrotech-eventos
KINESIS_STREAM_FEEDBACK=bistrotech-feedback
ENDPOINT_NAME=bistrotech-endpoint-v1
RETRAIN_THRESHOLD=50        # registros completos para trigger
IMPROVEMENT_THRESHOLD=0.05  # 5% mejora mínima para deploy
AWS_REGION=us-east-1
```

## Métricas de Producción (actualizar post-entrenamiento)

| Modelo | Métrica | Valor baseline | Valor actual |
|---|---|---|---|
| Modelo A (mozo) | RMSE propina_rate | [COMPLETAR] | [COMPLETAR] |
| Modelo B entrada | Hit Rate @ 3 | [COMPLETAR] | [COMPLETAR] |
| Modelo B principal | Hit Rate @ 3 | [COMPLETAR] | [COMPLETAR] |
| Modelo B postre | Hit Rate @ 3 | [COMPLETAR] | [COMPLETAR] |
| Modelo B bebida | Hit Rate @ 3 | [COMPLETAR] | [COMPLETAR] |
| Latencia promedio | ms | [COMPLETAR] | [COMPLETAR] |

## Equipo y Roles

| Rol | Responsabilidad |
|---|---|
| Data Engineer | Dataset crudo en S3, esquema de tablas |
| Data Scientist | Feature engineering, entrenamiento, métricas |
| MLOps Engineer | Pipelines, deploy, monitoreo, infraestructura AWS |