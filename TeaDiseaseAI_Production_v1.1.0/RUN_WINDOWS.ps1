param(
    [string]$PythonPath = "",
    [int]$Port = 8785,
    [string]$HostAddress = "127.0.0.1"
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

if (-not $PythonPath) {
    $LocalPython = Join-Path $Here ".venv\Scripts\python.exe"
    $PlantationPython = "H:\PlantationAI360\.venv\Scripts\python.exe"
    if (Test-Path $LocalPython) { $PythonPath = $LocalPython }
    elseif (Test-Path $PlantationPython) { $PythonPath = $PlantationPython }
    else { throw "No suitable Python found. Run SETUP_STANDALONE_WINDOWS.ps1 or pass -PythonPath." }
}

$env:PYTHONPATH = $Here
Write-Host "TeaGuard AI Production v1.1.0 + OpenCV Quality Gate" -ForegroundColor Green
Write-Host "Python: $PythonPath"
Write-Host "URL: http://$HostAddress`:$Port"
Write-Host "Press Ctrl+C to stop."
& $PythonPath -m uvicorn app.main:app --host $HostAddress --port $Port
