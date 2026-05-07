@echo off
REM Start BAET Complete Observation System
REM Starts paper trading, dashboard, and monitor

set PROJECT_DIR=%~dp0
set LOG_FILE=%PROJECT_DIR%logs\observation_start.log

echo ===============================================
echo BAET Observation System Launcher
echo ===============================================
echo.

REM Create logs directory if not exists
if not exist "%PROJECT_DIR%logs\paper" (
    mkdir "%PROJECT_DIR%logs\paper"
)

REM Check if already running
tasklist /fi "IMAGENAME eq python.exe" /fo csv 2>nul | find /i "baet.paper.engine" >nul
if not errorlevel 1 (
    echo [WARNING] Paper trading may already be running
    echo Check task manager or use: python scripts\paper_trading_manager.py status
    echo.
    pause
)

echo Starting services...
echo.

REM Start Paper Trading (Terminal 1)
echo [1/3] Starting Paper Trading Engine...
start "BAET Paper Trading" /min cmd /c "cd /d %PROJECT_DIR% && python scripts\start_observation.py"
timeout /t 3 /nobreak >nul

REM Start Dashboard (Terminal 2)
echo [2/3] Starting Dashboard...
start "BAET Dashboard" cmd /c "cd /d %PROJECT_DIR% && streamlit run src\baet\dashboard\app.py --server.port 8501 --theme.base dark"
timeout /t 3 /nobreak >nul

REM Start Monitor (Terminal 3 - Optional)
echo [3/3] Starting Monitor...
start "BAET Monitor" /min cmd /c "cd /d %PROJECT_DIR% && python scripts\monitor_paper_trading.py"

echo.
echo ===============================================
echo All services started!
echo ===============================================
echo.
echo Dashboard URL: http://localhost:8501
echo.
echo To check status: python scripts\paper_trading_manager.py status
echo To stop all: Use the Dashboard Control Panel or run:
echo   python scripts\paper_trading_manager.py stop
echo.
echo Logs are in: %PROJECT_DIR%logs\paper\
echo.
echo Press any key to close this window...
pause >nul
