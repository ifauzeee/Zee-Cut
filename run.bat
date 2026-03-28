@echo off
echo Starting Zee-Cut...
echo.
echo NOTE: This app requires Administrator privileges.
echo If prompted, click "Yes" to allow elevation.
echo.

:: Check if running as admin
net session >nul 2>&1
if errorlevel 1 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process python -ArgumentList 'main.py' -WorkingDirectory '%~dp0' -Verb RunAs"
) else (
    python main.py
)
