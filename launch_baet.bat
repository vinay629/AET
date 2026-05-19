@echo off
title BAET Intelligence Terminal
cls

echo ========================================================
echo   BAET QUANTITATIVE INTELLIGENCE TERMINAL
echo   Binance Adaptive Ensemble Trader
echo ========================================================
echo.

echo  [1/3] Activating environment...
cd /d "%~dp0"
call .venv\Scripts\activate
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  ERROR: Could not activate .venv. Run 'uv sync' first.
    echo.
    pause
    exit /b 1
)

echo.
echo  [2/3] Running bootstrap pipeline...
echo   - Fetching spot + derivatives data from Binance
echo   - Engineering technical and microstructure features
echo   - Generating dynamic ATR-scaled triple barrier labels
echo   - Training baseline model via PurgedKFold CV
echo   - Registering and promoting to production
echo.
python -m baet.scripts.bootstrap_pipeline --verbose

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  ERROR: Pipeline execution failed!
    echo  Check the logs above for network or data issues.
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo  [3/3] Starting dashboard server...
echo   Terminal URL: http://localhost:8501/terminal
echo   Press Ctrl+C to stop the server
echo.

:: Open browser after a short delay to let the server bind
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8501/terminal"

:: Start the FastAPI server (blocks until Ctrl+C)
python -m baet.dashboard.api.cli --host 0.0.0.0 --port 8501

echo.
echo  Server stopped.
pause
