REM ---THIS IS A FILE TO RUN THE SYSTEM AUTOMATICALLY CHOOSING THE CONDITIONS, 1 replicas for each terminal---
REM --- THIS IS NOT THE BENCHMARKING SCRIPT, FOR BENCHMARKING SEE benchmark_all.bat ---
REM ---for windows version ---
@echo off
REM --- configuration---
set TOLERANCE=10
set REPLICA_COUNT= 7
set NUM_REQUESTS=1000
set INTERVAL_MS=1000
set TIMEOUT=1000
set REDIS_HOST=192.168.1.189

REM --- create log file ---
if not exist "%CD%\logs" mkdir "%CD%\logs"

REM --- start replicas in separate folders ---
for /L %%i in (0,1,%REPLICA_COUNT% -1) do (
    start "Replica %%i" cmd /k docker run --rm --name replica%%i ^
        -v "%CD%\logs:/app/logs" ^
        image ^
        --replicaId=%%i ^
        --tolerance=%TOLERANCE% ^
        --replicaCount=%REPLICA_COUNT% ^
        --timeout=%TIMEOUT% ^
        --redis=%REDIS_HOST%
)

REM --- pause to start replicas ---
timeout /t 5

REM --- start client ---
docker run --rm --name pbft-client ^
    -v "%CD%\logs:/app/logs" ^
    image ^
    --client ^
    --tolerance=%TOLERANCE% ^
    --replicaCount=%REPLICA_COUNT% ^
    --requests=%NUM_REQUESTS% ^
    --interval=%INTERVAL_MS% ^
    --timeout=%TIMEOUT% ^
    --redis=%REDIS_HOST%
