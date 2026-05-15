# BAET Dashboard - One-Click Launcher
# Usage: Right-click -> "Run with PowerShell" or .\run_dashboard.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BAET Dashboard" -ForegroundColor White
Write-Host "  Binance Adaptive Ensemble Trader" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  URL: http://localhost:8501" -ForegroundColor Gray
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

try {
    uv run python scripts/run_dashboard.py
}
finally {
