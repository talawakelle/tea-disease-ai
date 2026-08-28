param([string]$PythonPath = "")
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here
if (-not $PythonPath) {
    $LocalPython = Join-Path $Here ".venv\Scripts\python.exe"
    $PlantationPython = "H:\PlantationAI360\.venv\Scripts\python.exe"
    if (Test-Path $LocalPython) { $PythonPath = $LocalPython }
    elseif (Test-Path $PlantationPython) { $PythonPath = $PlantationPython }
    else { throw "No suitable Python found. Pass -PythonPath." }
}
$env:PYTHONPATH = $Here
Write-Host "Running TeaGuard OpenCV production self-test..." -ForegroundColor Cyan
& $PythonPath "scripts\opencv_self_test.py"
if ($LASTEXITCODE -ne 0) { throw "OpenCV self-test failed." }
Write-Host "OpenCV quality engine is ready." -ForegroundColor Green
