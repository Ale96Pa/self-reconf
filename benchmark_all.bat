@echo off
setlocal enabledelayedexpansion

REM ===== BENCHMARKING WITH VARYING PARAMETERS =====

REM === BASE CONFIGURATION ===
set BASE_IMAGE=image
set REDIS_HOST=192.168.1.189
set TIMEOUT=1000
set REDIS_PORT=6379

REM === PARAMETERS ===
set REPLICA_COUNTS=4 10 19 31
set REQUESTS_LIST=1 10 100 1000 
set INTERVAL_LIST=50 200 500 1000

REM === MONITORING SCRIPT ===
set "BASE_DIR=%~dp0"
set "AVAIL_SCRIPT=%BASE_DIR%Analyzer\metrics\availability.py"

REM === MAIN FOLDER OF RESULTS ===
set RESULTS_DIR=%CD%\results
if not exist "%RESULTS_DIR%" mkdir "%RESULTS_DIR%"

REM === MAIN LOOP ===
for %%R in (%REPLICA_COUNTS%) do (
    set "R=%%R"
    set /A F=R - 1
    set /A F=F / 3

    for %%Q in (%REQUESTS_LIST%) do (
        for %%I in (%INTERVAL_LIST%) do (
            echo =======================================================
            echo TEST with REPLICAS=%%R  F=!F!  REQUESTS=%%Q  INTERVAL=%%I
            echo =======================================================

            set TEST_DIR=%RESULTS_DIR%\replicas_%%R_requests_%%Q_interval_%%I
            if not exist "!TEST_DIR!" mkdir "!TEST_DIR!"
            if not exist "!TEST_DIR!\logs" mkdir "!TEST_DIR!\logs"

            REM --- COMPUTE F DYNAMICALLY ---
            echo [DEBUG] Calcolato F=!F! per R=%%R

            REM --- START AVAILABILITY AND LATENCY MONITOR ---
            echo Avvio availability monitor...
            start "Availability Monitor" cmd /c python "!AVAIL_SCRIPT!" --f=!F! --host=%REDIS_HOST% --port=%REDIS_PORT% --outdir="!TEST_DIR!"

            REM --- WAIT BEFOR STARTING REPLICAS ---
            timeout /t 5 >nul
            
            REM --- START REPLICAS ---
            for /L %%i in (0,1,%%R-1) do (
                docker run -d --rm --name replica%%i -v "!TEST_DIR!\logs:/app/logs" %BASE_IMAGE% --replicaId=%%i --tolerance=!F! --replicaCount=%%R --timeout=%TIMEOUT% --redis=%REDIS_HOST%
            )

            REM --- PAUSE TO START CLIENT ---
            timeout /t 5 >nul

            REM --- START CLIENT ---
            docker run --rm --name pbft-client -v "!TEST_DIR!\logs:/app/logs" %BASE_IMAGE% --client --tolerance=!F! --replicaCount=%%R --requests=%%Q --interval=%%I --timeout=%TIMEOUT% --redis=%REDIS_HOST%


            

            REM === STOP CLIENT ===
            docker stop pbft-client >nul 2>&1

            REM === STOP REPLICAS ===
            for /L %%i in (0,1,%%R-1) do (
                docker stop replica%%i >nul 2>&1
            )

            REM === STOP AVAILABILITY MONITOR ===
            echo Arresto monitor di availability...
            taskkill /FI "WINDOWTITLE eq Availability Monitor" /F >nul 2>&1

            REM === PAUSE ===
            timeout /t 3 >nul

            echo Test completed for REPLICAS=%%R REQUESTS=%%Q INTERVAL=%%I
            echo Results saved in "!TEST_DIR!"
            echo -------------------------------------------------------

        )
    )
)

echo =======================================================
echo ALL TESTS COMPLETED, RESULTS SAVED IN: %RESULTS_DIR%
echo =======================================================
pause
