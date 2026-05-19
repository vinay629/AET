@echo off
title BAET Dashboard
echo ========================================
echo   BAET Dashboard - Binance Adaptive Ensemble Trader
echo ========================================
echo.
echo   URL: http://localhost:8501/terminal
echo   Press Ctrl+C to stop
echo ========================================
echo.

cd /d "%~dp0"

echo  Starting FastAPI server...
echo  (Run launch_baet.bat for the full pipeline + dashboard)
echo.

uv run python -m baet.dashboard.api.cli --host 0.0.0.0 --port 8501
pause
