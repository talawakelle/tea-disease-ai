param(
    [Parameter(Mandatory=$true)][string]$OldRoot
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$OldRoot = (Resolve-Path $OldRoot).Path
if ($OldRoot -eq $Here) { throw "OldRoot must point to the v1.0.0 folder, not this v1.1.0 folder." }

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Backup = Join-Path $Here "migration_backup_$Stamp"
New-Item -ItemType Directory -Force $Backup | Out-Null

$NewDb = Join-Path $Here "data\teaguard.db"
if (Test-Path $NewDb) {
    New-Item -ItemType Directory -Force (Join-Path $Backup "data") | Out-Null
    Copy-Item $NewDb (Join-Path $Backup "data\teaguard.db") -Force
}

$OldDb = Join-Path $OldRoot "data\teaguard.db"
if (Test-Path $OldDb) {
    New-Item -ItemType Directory -Force (Join-Path $Here "data") | Out-Null
    Copy-Item $OldDb $NewDb -Force
    Write-Host "Database copied." -ForegroundColor Green
} else {
    Write-Host "No old SQLite database found; continuing without DB migration." -ForegroundColor Yellow
}

$OldUploads = Join-Path $OldRoot "uploads"
$NewUploads = Join-Path $Here "uploads"
if (Test-Path $OldUploads) {
    New-Item -ItemType Directory -Force $NewUploads | Out-Null
    Copy-Item (Join-Path $OldUploads "*") $NewUploads -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Uploads copied." -ForegroundColor Green
}

$OldModel = Join-Path $OldRoot "models\tea_disease\v1.0.0"
$NewModel = Join-Path $Here "models\tea_disease\v1.0.0"
if (Test-Path $OldModel) {
    New-Item -ItemType Directory -Force $NewModel | Out-Null
    Copy-Item (Join-Path $OldModel "*.pt") $NewModel -Force -ErrorAction SilentlyContinue
    Copy-Item (Join-Path $OldModel "*.onnx") $NewModel -Force -ErrorAction SilentlyContinue
    Write-Host "Model artifacts copied." -ForegroundColor Green
}

Write-Host "" 
Write-Host "MIGRATION COPY COMPLETE" -ForegroundColor Green
Write-Host "Backup of any pre-existing v1.1 database: $Backup"
Write-Host "Start v1.1.0 once; its startup will create the new quality_assessments table automatically."
Write-Host "Legacy v1.0.0 scans remain visible and are labelled as legacy capture-quality records."
