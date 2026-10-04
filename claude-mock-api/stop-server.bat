@echo off
REM Stop the Claude Mock API Server
REM Finds and kills any running uvicorn process on port 8000

echo.
echo ========================================
echo   Claude Mock API Server - Stop
echo ========================================
echo.

REM Find process using port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    echo [INFO] Found process on port 8000: PID %%a
    taskkill /F /PID %%a
    if errorlevel 1 (
        echo [ERROR] Failed to stop process %%a
    ) else (
        echo [SUCCESS] Server stopped.
    )
    goto :done
)

echo [INFO] No server running on port 8000.

:done
echo.
pause
