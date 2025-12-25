@echo off
title StockBot Launcher
echo ===================================================
echo    STOCKBOT PRO - AUTO LAUNCHER
echo ===================================================

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from python.org
    pause
    exit
)

:: Install dependencies
echo [INFO] Checking and installing libraries...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit
)

echo.
echo [SUCCESS] All libraries are ready.
echo.
echo [INFO] Starting Telegram Bot...
start "StockBot Telegram" cmd /k "python app.py"

echo [INFO] Starting Web Interface...
start "StockBot Web" cmd /k "python web_app.py"

echo.
echo ===================================================
echo    BOT IS RUNNING
echo    - Telegram Bot: Running in new window
echo    - Web App: http://localhost:5000
echo ===================================================
echo.
echo You can close this launcher window now.
timeout /t 10
