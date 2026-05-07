@echo off
REM BAET Dashboard & Observation System Launcher
REM Usage: dashboard.bat [options]

set PROJECT_DIR=%~dp0
set PORT=8501
set THEME=dark
set MODE=menu

echo ================================================
echo BAET Dashboard & Observation System
echo ================================================
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

REM Parse command line arguments
:parse_args
if "%1"=="" goto show_menu
if /i "%1"=="--port" (
    set PORT=%2
    shift
    shift
    goto parse_args
)
if /i "%1"=="--light" (
    set THEME=light
    shift
    goto parse_args
)
if /i "%1"=="--dark" (
    set THEME=dark
    shift
    goto parse_args
)
if /i "%1"=="--observation" (
    set MODE=observation
    shift
    goto parse_args
)
if /i "%1"=="--dashboard-only" (
    set MODE=dashboard
    shift
    goto parse_args
)
if /i "%1"=="--help" (
    goto show_help
)
shift
goto parse_args

:show_help
echo Usage: dashboard.bat [options]
echo.
echo Options:
echo   --port PORT          Set dashboard port (default: 8501)
echo   --light              Use light theme (default: dark)
echo   --dark              Use dark theme
echo   --observation        Start complete observation system
echo   --dashboard-only    Start dashboard only (default)
echo   --help              Show this help message
echo.
echo Examples:
echo   dashboard.bat                           # Show menu
echo   dashboard.bat --observation              # Full observation system
echo   dashboard.bat --port 8502 --light     # Custom port + light theme
echo.
pause
exit /b 0

:show_menu
echo Choose mode:
echo   1. Dashboard Only (view existing logs)
echo   2. Complete Observation System (paper trading + dashboard + monitor)
echo.
set /p CHOICE="Enter choice (1 or 2): "
if "%CHOICE%"=="2" set MODE=observation
if "%CHOICE%"=="1" set MODE=dashboard

if "%MODE%"=="observation" goto start_observation
goto start_dashboard

:start_observation
echo.
echo ================================================
echo Starting Complete Observation System
echo ================================================
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
start "BAET Dashboard" cmd /c "cd /d %PROJECT_DIR% && streamlit run src\baet\dashboard\app.py --server.port %PORT% --theme.base %THEME%"

REM Start Monitor (Terminal 3 - Optional)
echo [3/3] Starting Monitor...
start "BAET Monitor" /min cmd /c "cd /d %PROJECT_DIR% && python scripts\monitor_paper_trading.py"

echo.
echo ================================================
echo All services started!
echo ================================================
echo.
echo Dashboard URL: http://localhost:%PORT%
echo.
echo To check status: python scripts\paper_trading_manager.py status
echo To stop all: Use the Dashboard Control Panel or run:
echo   python scripts\paper_trading_manager.py stop
echo.
echo Logs are in: %PROJECT_DIR%logs\paper\
echo.
echo Press any key to close this window...
pause >nul
exit /b 0

:start_dashboard
echo.
echo Starting BAET Dashboard...
echo   Port: %PORT%
echo   Theme: %THEME%
echo   URL: http://localhost:%PORT%
echo.

REM Change to project directory
cd /d %PROJECT_DIR%

REM Start Streamlit dashboard
if /i "%THEME%"=="light" (
    streamlit run src\baet\dashboard\app.py --server.port %PORT% --theme.base light
) else (
    streamlit run src\baet\dashboard\app.py --server.port %PORT% --theme.base dark
)

echo.
echo Dashboard stopped.
pause
