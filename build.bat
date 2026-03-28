@echo off
echo ============================================
echo   Zee-Cut - Build Script
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

:: Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)
echo      Done!
echo.

:: Create assets directory
if not exist "assets" mkdir assets

:: Build exe with PyInstaller
echo [2/3] Building executable...
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "Zee-Cut" ^
    --add-data "core;core" ^
    --hidden-import "scapy" ^
    --hidden-import "scapy.all" ^
    --hidden-import "scapy.layers.l2" ^
    --hidden-import "scapy.layers.inet" ^
    --hidden-import "customtkinter" ^
    --hidden-import "psutil" ^
    --collect-all "customtkinter" ^
    --collect-all "scapy" ^
    main.py

if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)
echo      Done!
echo.

echo [3/3] Build complete!
echo.
echo ============================================
echo   Output: dist\Zee-Cut.exe
echo ============================================
echo.
echo NOTE: You MUST install Npcap for network
echo scanning to work. Download from:
echo https://npcap.com/#download
echo.
echo Run the .exe as Administrator!
echo.
pause
