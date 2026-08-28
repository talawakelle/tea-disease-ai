param(
    [string]$PlantationRoot = "H:\PlantationAI360"
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ModelDir = Join-Path $Here "models\tea_disease\v1.0.0"
New-Item -ItemType Directory -Force $ModelDir | Out-Null

$PtSource = Join-Path $PlantationRoot "models\tea_disease\v1.0.0\tea_disease_yolo26n_v1.0.0.pt"
$OnnxSource = Join-Path $PlantationRoot "models\tea_disease\v1.0.0\tea_disease_yolo26n_v1.0.0.onnx"
if (-not (Test-Path $PtSource)) { throw "Validated PT model not found: $PtSource" }
Copy-Item $PtSource (Join-Path $ModelDir "tea_disease_yolo26n_v1.0.0.pt") -Force
if (Test-Path $OnnxSource) { Copy-Item $OnnxSource (Join-Path $ModelDir "tea_disease_yolo26n_v1.0.0.onnx") -Force }

$Python = Join-Path $PlantationRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "PlantationAI Python environment not found: $Python" }

Write-Host ""
Write-Host "MODEL COPIED" -ForegroundColor Green
Get-ChildItem $ModelDir | Select-Object Name,Length,LastWriteTime
Write-Host ""
Write-Host "VERIFYING PRODUCTION APP IMPORTS..." -ForegroundColor Cyan
& $Python -c "import fastapi, sqlalchemy, PIL, ultralytics, cv2; print('IMPORT CHECK: PASSED | OpenCV', cv2.__version__)"
if ($LASTEXITCODE -ne 0) { throw "Import check failed. Install requirements.txt into the PlantationAI virtual environment." }

Write-Host ""
Write-Host "INSTALLATION LINKED TO EXISTING PLANTATIONAI ENVIRONMENT" -ForegroundColor Green
Write-Host "Run with: .\RUN_WINDOWS.ps1 -PythonPath `"$Python`""
