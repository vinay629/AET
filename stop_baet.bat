@echo off
REM BAET Complete Trading System - STOP ALL
REM Stops paper trading, dashboard, and monitor

echo ==============================================
echo BAET System - STOP ALL SERVICES
echo ==============================================
echo.

echo Checking for running BAET processes...
echo.

REM Stop using Python manager (preferred method)
python scripts\paper_trading_manager.py stop 2>nul
if not errorlevel 1 (
    echo [OK] Paper trading stopped via manager
) else (
    echo [INFO] Manager method failed, trying taskkill...
    
    REM Kill paper trading processes
    taskkill /fi "IMAGENAME eq python.exe" /fi "WINDOWTITLE eq BAET*" >nul 2>&1
    taskkill /fi "COMMANDLINE eq *baet.paper*" >nul 2>&1
    
    echo [OK] Processes killed
)

REM Kill Streamlit dashboard
taskkill /fi "WINDOWTITLE eq BAET Dashboard*" >nul 2>&1
taskkill /im streamlit.exe >nul 2>&1

REM Kill monitor
taskkill /fi "WINDOWTITLE eq BAET Monitor*" >nul 2>&1

echo.
echo ==============================================
echo All BAET Services Stopped
echo ==============================================
echo.
echo Dashboard and monitors should now be closed.
echo Check task manager to confirm all processes stopped.
echo.
pause
