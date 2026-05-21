# BistroTech — Infraestructura AWS con Terraform

Levanta y destruye **toda** la infraestructura de producción de BistroTech con un solo comando.

---

## Prerrequisitos

| Herramienta | Versión mínima | Verificación |
|---|---|---|
| [Terraform](https://www.terraform.io/downloads) | >= 1.5 | `terraform version` |
| [AWS CLI](https://aws.amazon.com/cli/) | >= 2.x | `aws --version` |
| Python | >= 3.10 | `python --version` |
| Credenciales AWS | — | `aws sts get-caller-identity` |

### Configurar credenciales AWS

```powershell
aws configure
# AWS Access Key ID: <tu-key>
# AWS Secret Access Key: <tu-secret>
# Default region name: us-east-1
# Default output format: json
```

Necesitás permisos sobre: S3, SageMaker, Lambda, API Gateway, Kinesis, CloudWatch, IAM.

---

## Primer deploy

```powershell
# Desde la raíz del proyecto:
.\terraform\scripts\deploy.ps1
```

El script hace todo en orden automáticamente:

1. Verifica que Terraform y AWS CLI estén instalados y configurados
2. Verifica que existe `models/bistrotech-model.tar.gz`; si no, ejecuta `infrastructure/package_model.py`
3. Crea el bucket S3 e IAM Role (fase previa, `-target`)
4. Sube el modelo empaquetado a S3
5. Ejecuta `terraform plan` completo y muestra los cambios
6. Pide confirmación antes de aplicar
7. Ejecuta `terraform apply`
8. Imprime los outputs (endpoint, API URL, dashboard) y un comando `curl` de prueba

---

## Destruir todo

```powershell
# Desde la raíz del proyecto:
.\terraform\scripts\destroy.ps1
```

Pide confirmación explícita (`CONFIRMAR`) antes de ejecutar `terraform destroy`.

> **Nota:** El bucket S3 puede quedar con datos (modelos, métricas). Terraform no elimina buckets no vacíos por seguridad. El script muestra los comandos para vaciarlo y eliminarlo manualmente.

---

## Qué hace cada módulo

| Módulo | Recursos creados | Propósito |
|---|---|---|
| `iam` | `SageMakerBistroTechRole` | Role único para SageMaker y Lambda con acceso a S3, Kinesis, CloudWatch |
| `s3` | Bucket `bistrotech-models-<account_id>` | Data lake: modelos, métricas baseline, contadores de retrain |
| `kinesis` | `bistrotech-eventos`, `bistrotech-feedback` | Ingesta de eventos en tiempo real con retención de 24h |
| `sagemaker` | Model + EndpointConfig + Endpoint | Endpoint XGBoost en tiempo real para inferencia |
| `lambda` | 3 funciones + EventBridge rule | Trigger mini-batch, deploy automático, API handler |
| `api_gateway` | REST API `/predict` (POST) | Entry point externo hacia el endpoint SageMaker |
| `cloudwatch` | 2 alarmas + 1 dashboard | Monitoreo de drift y errores del endpoint |

---

## Verificar que el endpoint funciona

Después del deploy, el script imprime la URL. También podés obtenerla con:

```powershell
cd terraform/
terraform output api_url
```

### Comando curl de prueba

```bash
curl -X POST "https://XXXX.execute-api.us-east-1.amazonaws.com/prod/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "id_mesa": 42,
    "comensales": [{
      "id_persona_en_mesa": 1,
      "franja_etaria_persona": "adulto",
      "cant_acompanantes": 3,
      "motivo_visita": "negocios",
      "restriccion_alimentaria": "ninguna",
      "es_repetidor": true,
      "visitas_previas": 5,
      "ticket_promedio_historico": 3200.0,
      "orden_de_pedido": 1
    }],
    "dia_semana": 1,
    "franja_horaria": "mediodia"
  }'
```

Respuesta esperada:
```json
{
  "id_mesa": 42,
  "mozos_recomendados": [
    {"id_mozo": 3, "propina_rate_esperado": 0.18, "rank": 1}
  ],
  "modelo_version": "v1"
}
```

---

## Costos estimados (us-east-1, uso académico)

| Recurso | Tipo | Costo estimado/mes |
|---|---|---|
| SageMaker Endpoint | `ml.m5.large` (24/7) | ~$120 |
| Kinesis Streams | 2 streams × 1 shard | ~$30 |
| Lambda | 3 funciones, invocaciones mínimas | ~$1 |
| API Gateway | REST API, tráfico mínimo | ~$1 |
| S3 | Almacenamiento modelos (~1 GB) | ~$0.02 |
| CloudWatch | Alarmas + dashboard | ~$3 |
| **Total estimado** | | **~$155/mes** |

> **Para el TP:** destruir con `.\terraform\scripts\destroy.ps1` al terminar de presentar. El mayor costo es el endpoint SageMaker activo 24/7.

---

## Troubleshooting — Errores más comunes

### 1. `Error: data.aws_s3_object.model_tar: object not found`

**Causa:** El modelo no fue subido a S3 antes de ejecutar `terraform plan`.

**Solución:** Siempre usar `.\terraform\scripts\deploy.ps1` en lugar de ejecutar Terraform directamente. El script hace el upload antes del plan.

```powershell
# Verificar que el modelo existe en S3:
aws s3 ls s3://bistrotech-models-<ACCOUNT_ID>/models/
```

---

### 2. `Error creating SageMaker Endpoint: ValidationException: Could not find model`

**Causa:** El `aws_sagemaker_model` no se creó correctamente o el `model_data_url` apunta a un archivo inexistente.

**Solución:**
```powershell
# Verificar que el tar.gz existe:
aws s3 ls s3://bistrotech-models-<ACCOUNT_ID>/models/bistrotech-model.tar.gz

# Si no existe, generarlo y subirlo:
python infrastructure/package_model.py
aws s3 cp models/bistrotech-model.tar.gz s3://bistrotech-models-<ACCOUNT_ID>/models/
```

---

### 3. `Error: IAM Role SageMakerBistroTechRole already exists`

**Causa:** Una ejecución anterior dejó el role sin destruirlo (o fue creado manualmente).

**Solución:**
```powershell
# Opción A: importar el role existente al estado de Terraform
cd terraform/
terraform import module.iam.aws_iam_role.sagemaker_bistrotech SageMakerBistroTechRole

# Opción B: eliminar el role manualmente y re-aplicar
aws iam delete-role --role-name SageMakerBistroTechRole
```

---

## Estructura de archivos Terraform

```
terraform/
├── main.tf               # Provider, backend local, llamadas a módulos
├── variables.tf          # Variables con defaults
├── outputs.tf            # Outputs: account_id, api_url, dashboard_url...
├── terraform.tfvars      # Valores concretos (NO commitear)
├── modules/
│   ├── iam/              # IAM Role + políticas
│   ├── s3/               # Bucket + versionado + objetos iniciales
│   ├── kinesis/          # Streams de eventos y feedback
│   ├── sagemaker/        # Model + EndpointConfig + Endpoint
│   ├── lambda/           # 3 funciones + EventBridge + código Python
│   ├── api_gateway/      # REST API /predict (POST) → Lambda Proxy
│   └── cloudwatch/       # Alarmas drift + errors + dashboard
└── scripts/
    ├── deploy.ps1         # Un comando para levantar todo
    └── destroy.ps1        # Un comando para destruir todo
```
