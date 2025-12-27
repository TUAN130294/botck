@echo off
REM ============================================================================
REM MASTER SCRIPT - TRAIN + BACKTEST UNION STOCKS
REM ============================================================================
REM
REM This will:
REM   1. Create union list (TOP62 + VN100)
REM   2. Train all ~102 stocks with GPU parallel
REM   3. Backtest all models
REM   4. Analyze and identify PASSED stocks
REM
REM Expected time: 60-70 minutes
REM ============================================================================

echo.
echo ================================================================================
echo                   STARTING FULL PIPELINE
echo ================================================================================
echo.
echo Started: %DATE% %TIME%
echo.

cd /d e:\botck

echo ================================================================================
echo STEP 1/4: Creating Union List
echo ================================================================================
echo.
python create_union_list.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create union list
    pause
    exit /b 1
)
echo.
echo [OK] Union list created
echo.
timeout /t 3 /nobreak

echo ================================================================================
echo STEP 2/4: Training Models (GPU Parallel - ~30-40 min)
echo ================================================================================
echo.
echo This will take 30-40 minutes...
echo You can monitor GPU usage: nvidia-smi -l 2
echo.
python train_union_parallel.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Training failed
    pause
    exit /b 1
)
echo.
echo [OK] Training complete
echo.
timeout /t 3 /nobreak

echo ================================================================================
echo STEP 3/4: Backtesting Models (~30 min)
echo ================================================================================
echo.
echo This will take ~30 minutes...
echo.
python backtest_simple.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Backtest failed
    pause
    exit /b 1
)
echo.
echo [OK] Backtest complete
echo.
timeout /t 3 /nobreak

echo ================================================================================
echo STEP 4/4: Analyzing Results
echo ================================================================================
echo.
python analyze_final_results.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Analysis failed
    pause
    exit /b 1
)
echo.
echo [OK] Analysis complete
echo.

echo ================================================================================
echo                   ALL DONE!
echo ================================================================================
echo.
echo Finished: %DATE% %TIME%
echo.
echo RESULTS:
echo   - PASSED_STOCKS.txt         ^<-- Final list of profitable stocks
echo   - training_results_union_*.csv
echo   - backtest_results_simple_*.csv
echo   - models/*.pt               ^<-- All trained models
echo.
echo NEXT STEPS:
echo   1. Review PASSED_STOCKS.txt
echo   2. Setup paper trading dashboard
echo   3. Start trading!
echo.
echo ================================================================================

pause
