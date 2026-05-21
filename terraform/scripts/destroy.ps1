# destroy.ps1 — Destruye toda la infraestructura BistroTech en AWS
# Uso: desde la raiz del proyecto → .\terraform\scripts\destroy.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TerraformDir = Split-Path -Parent $ScriptDir

Write-Host ""
Write-Host "============================================" -ForegroundColor Red
Write-Host "   BistroTech — Destruir infraestructura AWS" -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Red
Write-Host ""
Write-Host "  ⚠️  ADVERTENCIA: Esto destruirá TODOS los recursos de AWS de BistroTech:" -ForegroundColor Red
Write-Host "     • SageMaker Endpoint, Model y EndpointConfiguration" -ForegroundColor Red
Write-Host "     • Lambda Functions (trigger, deploy, api-handler)" -ForegroundColor Red
Write-Host "     • API Gateway REST API" -ForegroundColor Red
Write-Host "     • Kinesis Data Streams (eventos + feedback)" -ForegroundColor Red
Write-Host "     • CloudWatch Alarms y Dashboard" -ForegroundColor Red
Write-Host "     • IAM Role SageMakerBistroTechRole" -ForegroundColor Red
Write-Host "     • Bucket S3 (vacío — ver nota abajo)" -ForegroundColor Red
Write-Host ""

$confirmation = Read-Host "Escribí CONFIRMAR para continuar (cualquier otra cosa cancela)"
if ($confirmation -ne "CONFIRMAR") {
    Write-Host "`nOperación cancelada. No se modificó ningún recurso." -ForegroundColor Yellow
    exit 0
}

Set-Location $TerraformDir

Write-Host "`nEjecutando terraform destroy..." -ForegroundColor Yellow
terraform destroy -auto-approve
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error durante terraform destroy. Algunos recursos pueden haber quedado activos. Revisar la consola AWS."
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   ✅ Todos los recursos han sido eliminados." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# Verificar recursos remanentes
Write-Host "Verificando que no quedan recursos activos..." -ForegroundColor Yellow
try {
    $ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text 2>$null)

    # Verificar endpoint SageMaker
    $endpoints = (aws sagemaker list-endpoints --query "Endpoints[?contains(EndpointName,'bistrotech')]" --output json 2>$null | ConvertFrom-Json)
    if ($endpoints.Count -eq 0) {
        Write-Host "  ✅ SageMaker endpoints: ninguno activo" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  SageMaker endpoints aún activos: $($endpoints | ConvertTo-Json -Compress)" -ForegroundColor Yellow
    }

    # Recordar bucket S3
    $S3_BUCKET = "bistrotech-models-$ACCOUNT_ID"
    Write-Host ""
    Write-Host "💡 NOTA IMPORTANTE sobre el bucket S3:" -ForegroundColor Yellow
    Write-Host "   El bucket S3 puede haber quedado con datos (modelos, métricas, contadores)." -ForegroundColor Yellow
    Write-Host "   Terraform no puede eliminar buckets no vacíos por seguridad." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   Para verificar su contenido:" -ForegroundColor White
    Write-Host "     aws s3 ls s3://$S3_BUCKET/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   Para vaciarlo y eliminarlo manualmente:" -ForegroundColor White
    Write-Host "     aws s3 rm s3://$S3_BUCKET/ --recursive" -ForegroundColor Cyan
    Write-Host "     aws s3 rb s3://$S3_BUCKET/" -ForegroundColor Cyan
} catch {
    Write-Host "  (No se pudo verificar el estado final — revisar la consola AWS manualmente)" -ForegroundColor Gray
}
