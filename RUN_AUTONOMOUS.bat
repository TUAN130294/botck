@echo off
REM ========================================
REM Autonomous Paper Trading - Quick Start
REM ========================================

echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║     AUTONOMOUS PAPER TRADING SYSTEM                       ║
echo ║     Quick Start Script                                    ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

REM Change to script directory
cd /d "%~dp0"

echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python 3.8+
    pause
    exit /b 1
)
echo ✅ Python found

echo.
echo [2/3] Running tests...
echo.
python test_autonomous_quick.py

if errorlevel 1 (
    echo.
    echo ❌ Tests failed! Please fix issues above
    pause
    exit /b 1
)

echo.
echo [3/3] Starting autonomous trading system...
echo.
echo Dashboard will open at: http://localhost:8000/autonomous
echo Press Ctrl+C to stop
echo.

REM Start browser after 3 seconds
start /b timeout /t 3 /nobreak >nul && start http://localhost:8000/autonomous

REM Run the system
python run_autonomous_paper_trading.py

pause
