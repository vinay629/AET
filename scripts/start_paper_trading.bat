@echo off
REM Start paper trading with automatic restart loop
REM For M4.4 observation window (7-14 days continuous operation)

echo ================================================
echo BAET Paper Trading - Continuous Operation
echo M4.4 Observation Window
echo ================================================
echo.

set RESTART_DELAY=10
set MAX_RESTARTS=1000
set RESTART_COUNT=0

:loop
set /a RESTART_COUNT+=1
echo [%date% %time%] Starting paper trading (attempt %RESTART_COUNT%)...
echo.

python -m baet.paper.engine --config config/paper.yaml

echo.
echo [%date% %time%] Paper trading stopped with exit code %ERRORLEVEL%
echo [%date% %time%] Restarting in %RESTART_DELAY% seconds...
echo.

timeout /t %RESTART_DELAY% /nobreak > nul

goto loop
