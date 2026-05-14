@echo off
title BAET Dashboard
echo ========================================
echo   BAET Dashboard - Binance Adaptive Ensemble Trader
echo ========================================
echo.

cd /d "%~dp0"

echo Starting dashboard server...
start http://localhost:8501
uv run python scripts/run_dashboard.py

echo.
echo Dashboard stopped.
pause
