@echo off
REM BAET Dashboard Launcher
REM This batch file starts the BAET trading dashboard

echo Starting BAET Dashboard...
echo.

REM Change to the project directory
cd /d "%~dp0"

REM Activate conda environment if it exists
REM Uncomment and modify the next line if you have a specific conda environment
REM call conda activate baet-env

REM Start the dashboard with Streamlit
streamlit run src/baet/dashboard/app.py --server.headless true --server.port 8501

echo.
echo Dashboard stopped.
pause