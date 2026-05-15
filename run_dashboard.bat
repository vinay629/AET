@echo off
title BAET Dashboard
echo ========================================
echo   BAET Dashboard - Binance Adaptive Ensemble Trader
echo ========================================
echo.
echo   URL: http://localhost:8501
echo   Press Ctrl+C to stop
echo ========================================
echo.

cd /d "%~dp0"

uv run python scripts/run_dashboard.py

echo.
echo Dashboard stopped.
pause
