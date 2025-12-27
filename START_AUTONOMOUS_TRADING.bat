@echo off
chcp 65001 > nul
echo.
echo ╔══════════════════════════════════════════════════════════════════════════════╗
echo ║                    AUTONOMOUS PAPER TRADING SYSTEM                           ║
echo ║                    Hệ thống giao dịch tự động 100%%                           ║
echo ╚══════════════════════════════════════════════════════════════════════════════╝
echo.
echo 📊 THÔNG TIN HỆ THỐNG:
echo    • Portfolio ban đầu: 100,000,000 VND
echo    • Số mã tối đa: 8 cổ phiếu (12.5%% mỗi mã)
echo    • Take Profit: +15%%
echo    • Trailing Stop: -5%% từ đỉnh
echo    • Stop Loss: -5%%
echo.
echo 🤖 AGENTS:
echo    • Alex (📊): Phân tích kỹ thuật
echo    • Bull (🐂): Góc nhìn lạc quan
echo    • Bear (🐻): Cảnh báo rủi ro
echo    • RiskDoctor (⚕️): Kiểm tra danh mục
echo    • Chief (👔): Quyết định cuối cùng
echo.
echo 🚀 ĐANG KHỞI ĐỘNG...
echo.

REM Kill any existing Python processes
taskkill /F /IM python.exe >nul 2>&1

REM Wait 2 seconds
timeout /t 2 /nobreak > nul

REM Start server
echo ✅ Starting server on http://localhost:8001/autonomous
echo.
python run_autonomous_paper_trading.py

pause
