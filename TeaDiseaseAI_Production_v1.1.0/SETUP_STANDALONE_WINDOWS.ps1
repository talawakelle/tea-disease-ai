param([string]$Python311 = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here
if (-not (Test-Path $Python311)) { throw "Python 3.11 not found at $Python311" }
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $Python311 -m venv .venv }
$Py = Join-Path $Here ".venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r requirements.txt
Write-Host "Standalone environment created." -ForegroundColor Green
Write-Host "Copy the validated model into models\tea_disease\v1.0.0, then run .\RUN_WINDOWS.ps1"
