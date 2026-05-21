# deploy.ps1 — Despliega la infraestructura BistroTech en AWS con un solo comando
# Uso: desde la raiz del proyecto → .\terraform\scripts\deploy.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TerraformDir = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $TerraformDir

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   BistroTech — Deploy en AWS con Terraform" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 1. Verificar que Terraform está instalado
Write-Host "`n[Paso 1/6] Verificando Terraform..." -ForegroundColor Yellow
if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
    Write-Error "Terraform no encontrado. Instalarlo desde: https://www.terraform.io/downloads"
    exit 1
}
$tfVersion = (terraform version -json | ConvertFrom-Json).terraform_version
Write-Host "  ✅ Terraform $tfVersion encontrado." -ForegroundColor Green

# 2. Verificar AWS CLI y credenciales
Write-Host "`n[Paso 2/6] Verificando credenciales AWS..." -ForegroundColor Yellow
try {
    $callerIdentity = aws sts get-caller-identity --output json | ConvertFrom-Json
    $ACCOUNT_ID = $callerIdentity.Account
    $ARN = $callerIdentity.Arn
    Write-Host "  ✅ Account: $ACCOUNT_ID" -ForegroundColor Green
    Write-Host "  ✅ Identity: $ARN" -ForegroundColor Green
} catch {
    Write-Error "AWS CLI no configurado o credenciales inválidas. Ejecutar: aws configure"
    exit 1
}

# 3. Verificar/generar model.tar.gz
Write-Host "`n[Paso 3/6] Verificando modelo empaquetado..." -ForegroundColor Yellow
$MODEL_PATH = Join-Path $ProjectRoot "models\bistrotech-model.tar.gz"
if (-not (Test-Path $MODEL_PATH)) {
    Write-Host "  ⚠️  Modelo no encontrado en $MODEL_PATH" -ForegroundColor Yellow
    Write-Host "  → Ejecutando infrastructure\package_model.py..." -ForegroundColor Yellow
    $PackageScript = Join-Path $ProjectRoot "infrastructure\package_model.py"
    python $PackageScript
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Error al empaquetar el modelo. Revisar infrastructure/package_model.py"
        exit 1
    }
}
Write-Host "  ✅ Modelo listo: $MODEL_PATH" -ForegroundColor Green

# 4. Inicializar Terraform
Write-Host "`n[Paso 4/6] Inicializando Terraform..." -ForegroundColor Yellow
Set-Location $TerraformDir
terraform init
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error en terraform init."
    exit 1
}

# 5. Crear S3 e IAM primero (necesarios antes de subir el modelo)
Write-Host "`n[Paso 5/6] Creando bucket S3 e IAM Role (fase previa)..." -ForegroundColor Yellow
Write-Host "  Esto permite subir el modelo antes de crear el endpoint SageMaker." -ForegroundColor Gray
terraform apply -target=module.iam -target=module.s3 -auto-approve
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error al crear IAM/S3. Revisar los mensajes de Terraform."
    exit 1
}

# Subir modelo a S3
$S3_BUCKET = "bistrotech-models-$ACCOUNT_ID"
Write-Host "`n  Subiendo modelo a s3://$S3_BUCKET/models/..." -ForegroundColor Yellow
aws s3 cp $MODEL_PATH "s3://$S3_BUCKET/models/bistrotech-model.tar.gz" --no-progress
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error al subir el modelo a S3. Verificar que el bucket existe."
    exit 1
}
Write-Host "  ✅ Modelo subido a S3." -ForegroundColor Green

# 6. Plan completo
Write-Host "`n[Paso 6/6] Planificando deploy completo de todos los módulos..." -ForegroundColor Yellow
terraform plan -out=tfplan
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error en terraform plan."
    exit 1
}

# Confirmar con el usuario
Write-Host ""
$confirmation = Read-Host "¿Continuar con el deploy? (s/n)"
if ($confirmation -ne "s") {
    Write-Host "Deploy cancelado por el usuario." -ForegroundColor Yellow
    Remove-Item -Force tfplan -ErrorAction SilentlyContinue
    exit 0
}

# Apply completo
terraform apply tfplan
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error en terraform apply."
    exit 1
}
Remove-Item -Force tfplan -ErrorAction SilentlyContinue

# Resultados
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   ✅ Deploy completado exitosamente!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
terraform output

# Comando curl de prueba
$API_URL = (terraform output -raw api_url 2>$null)
if ($API_URL) {
    Write-Host ""
    Write-Host "📡 Comando de prueba (copiar y pegar):" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "curl -X POST `"$API_URL`" ``" -ForegroundColor White
    Write-Host "  -H `"Content-Type: application/json`" ``" -ForegroundColor White
    Write-Host "  -d `'{" -ForegroundColor White
    Write-Host "    `"id_mesa`": 42," -ForegroundColor White
    Write-Host "    `"comensales`": [{" -ForegroundColor White
    Write-Host "      `"id_persona_en_mesa`": 1," -ForegroundColor White
    Write-Host "      `"franja_etaria_persona`": `"adulto`"," -ForegroundColor White
    Write-Host "      `"cant_acompanantes`": 3," -ForegroundColor White
    Write-Host "      `"motivo_visita`": `"negocios`"," -ForegroundColor White
    Write-Host "      `"restriccion_alimentaria`": `"ninguna`"," -ForegroundColor White
    Write-Host "      `"es_repetidor`": true," -ForegroundColor White
    Write-Host "      `"visitas_previas`": 5," -ForegroundColor White
    Write-Host "      `"ticket_promedio_historico`": 3200.0," -ForegroundColor White
    Write-Host "      `"orden_de_pedido`": 1" -ForegroundColor White
    Write-Host "    }]," -ForegroundColor White
    Write-Host "    `"dia_semana`": 1," -ForegroundColor White
    Write-Host "    `"franja_horaria`": `"mediodia`"" -ForegroundColor White
    Write-Host "  }'" -ForegroundColor White
}
