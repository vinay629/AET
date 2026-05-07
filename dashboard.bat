@echo off
REM Start BAET Dashboard with Control Panel
REM Usage: dashboard.bat [options]

set DASHBOARD_DIR=%~dp0
set DASHBOARD_SCRIPT=%DASHBOARD_DIR%scripts\run_dashboard.py

echo ================================================
echo BAET Dashboard Launcher
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

REM Check if streamlit is installed
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
set PORT=8501
set THEME=dark

:parse_args
if "%1"=="" goto start_dashboard
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
if /i "%1"=="--help" (
    goto show_help
)
shift
goto parse_args

:show_help
echo Usage: dashboard.bat [options]
echo.
echo Options:
echo   --port PORT    Set dashboard port (default: 8501)
echo   --light        Use light theme (default: dark)
echo   --help         Show this help message
echo.
echo Examples:
echo   dashboard.bat
echo   dashboard.bat --port 8502
echo   dashboard.bat --light
echo.
pause
exit /b 0

:start_dashboard
echo Starting BAET Dashboard...
echo   Port: %PORT%
echo   Theme: %THEME%
echo   URL: http://localhost:%PORT%
echo.

REM Change to project directory
cd /d %DASHBOARD_DIR%

REM Start Streamlit dashboard
streamlit run src\baet\dashboard\app.py --server.port %PORT% --theme %THEME%

echo.
echo Dashboard stopped.
pause
