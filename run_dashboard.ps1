# BAET Dashboard - One-Click Launcher
# Usage: Right-click -> "Run with PowerShell" or .\run_dashboard.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BAET Dashboard" -ForegroundColor White
Write-Host "  Binance Adaptive Ensemble Trader" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$port = if ($env:BAET_DASHBOARD_PORT) { $env:BAET_DASHBOARD_PORT } else { "8501" }
$url = "http://localhost:$port"

Write-Host "Starting dashboard server..." -ForegroundColor Yellow

# Start browser after 2s delay in background
$browserJob = Start-Job -ScriptBlock {
    param($url)
    Start-Sleep -Seconds 2
    Start-Process $url
} -ArgumentList $url

try {
    uv run python scripts/run_dashboard.py
}
 finally {
    Stop-Job $browserJob -ErrorAction SilentlyContinue
    Remove-Job $browserJob -ErrorAction SilentlyContinue
    Write-Host "`nDashboard stopped." -ForegroundColor Yellow
}
