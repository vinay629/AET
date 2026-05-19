# BAET Quantitative Intelligence Terminal — One-Click Launcher
# Usage: Right-click -> "Run with PowerShell" or: .\launch_baet.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  BAET QUANTITATIVE INTELLIGENCE TERMINAL" -ForegroundColor Cyan
Write-Host "  Binance Adaptive Ensemble Trader" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Activate environment ──
Write-Host " [1/3] Activating environment..." -ForegroundColor Yellow
Set-Location $ProjectRoot

if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .venv\Scripts\Activate.ps1
} else {
    Write-Host "ERROR: .venv not found. Run 'uv sync' first." -ForegroundColor Red
    pause
    exit 1
}

# ── Step 2: Run bootstrap pipeline ──
Write-Host ""
Write-Host " [2/3] Running bootstrap pipeline..." -ForegroundColor Yellow
Write-Host "  - Fetching spot + derivatives data from Binance"
Write-Host "  - Engineering technical and microstructure features"
Write-Host "  - Generating dynamic ATR-scaled triple barrier labels"
Write-Host "  - Training baseline model via PurgedKFold CV"
Write-Host "  - Registering and promoting to production"
Write-Host ""

python -m baet.scripts.bootstrap_pipeline --verbose

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Pipeline execution failed!" -ForegroundColor Red
    Write-Host "Check the logs above for network or data issues." -ForegroundColor Red
    pause
    exit $LASTEXITCODE
}

# ── Step 3: Start dashboard server ──
Write-Host ""
Write-Host " [3/3] Starting dashboard server..." -ForegroundColor Yellow
Write-Host "  Terminal URL: http://localhost:8501/terminal" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop the server"
Write-Host ""

# Open browser after a short delay
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:8501/terminal"
} | Out-Null

# Start the FastAPI server (blocks until Ctrl+C)
python -m baet.dashboard.api.cli --host 0.0.0.0 --port 8501

Write-Host ""
Write-Host "Server stopped." -ForegroundColor Yellow
pause
