@echo off
REM BAET Complete Trading System Launcher
REM Starts paper trading, dashboard, and monitor in one complete window

set PROJECT_DIR=%~dp0
set PORT=8501
set THEME=dark

echo ==============================================
echo BAET Complete Trading System
echo ==============================================
echo.

REM Change to project directory
cd /d %PROJECT_DIR%

REM Check if already running
tasklist /fi "IMAGENAME eq python.exe" /fo csv 2>nul | find /i "baet" >nul
if not errorlevel 1 (
    echo [WARNING] BAET may already be running!
    echo Check task manager or use: python scripts\paper_trading_manager.py status
    echo.
    set /p CONTINUE="Continue anyway? (y/n): "
    if /i not "%CONTINUE%"=="y" (
        exit /b 0
    )
)

echo Checking requirements...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.13+ and try again
    pause
    exit /b 1
)

REM Check if Streamlit is installed
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Streamlit not found. Installing...
    pip install streamlit plotly
    if errorlevel 1 (
        echo [ERROR] Failed to install streamlit
        pause
        exit /b 1
    )
)

echo [OK] Python and Streamlit are available
echo.

REM Create required directories
if not exist "logs\paper" (
    mkdir "logs\paper"
    echo [OK] Created logs\paper directory
)

if not exist "data" (
    mkdir "data"
    echo [OK] Created data directory
)

echo.
echo ==============================================
echo Starting Complete Trading System
echo ==============================================
echo.

REM Start Paper Trading Engine (Background)
echo [1/3] Starting Paper Trading Engine with Simulation...
start "BAET Paper Trading" /min cmd /c "python scripts\start_observation.py"
timeout /t 3 /nobreak >nul

REM Start Dashboard with Control Panel (Background)
echo [2/3] Starting Dashboard with Control Panel...
start "BAET Dashboard" cmd /c "streamlit run src\baet\dashboard\app.py --server.port %PORT% --theme.base %THEME%"
timeout /t 3 /nobreak >nul

REM Start Monitor (Background, Optional)
echo [3/3] Starting System Monitor...
start "BAET Monitor" /min cmd /c "python scripts\monitor_paper_trading.py"
timeout /t 2 /nobreak >nul

echo.
echo ==============================================
echo All Services Started Successfully!
echo ==============================================
echo.
echo Dashboard URL: http://localhost:%PORT%
echo Dashboard Theme: %THEME%
echo.
echo Services Running:
echo   - Paper Trading Engine (with simulation)
echo   - Streamlit Dashboard (with Control Panel)
echo   - System Monitor (background)
echo.
echo Control Panel Features:
echo   ✓ Start/Stop Paper Trading
echo   ✓ Emergency Stop Button
echo   ✓ Status Indicator (running/stopped)
echo   ✓ Settings Panel (balance, interval)
echo.
echo To check status: python scripts\paper_trading_manager.py status
echo To stop all: Use Dashboard Control Panel or:
echo   python scripts\paper_trading_manager.py stop
echo.
echo Logs are in: %PROJECT_DIR%logs\paper\
echo Observation Log: docs\M4.4_OBSERVATION_LOG.md
echo Daily Checklist: docs\M4.4_DAILY_CHECKLIST.md
echo.
echo Press any key to minimize this window...
pause >nul

REM Minimize this window (optional - user can close)
echo.
echo System is running! Use the Dashboard Control Panel to manage.
echo This window can be closed - services run independently.
echo.
pause
