@echo off
REM Claude Mock API Server Launcher
REM This script creates/activates a virtual environment and starts the server

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Claude Mock API Server Launcher
echo ========================================
echo.

REM Navigate to the script directory
cd /d "%~dp0"

REM Check if .venv exists
if not exist ".venv\" (
    echo [INFO] Virtual environment not found. Creating .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        echo [ERROR] Make sure Python 3.10+ is installed and in PATH.
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created.
    echo.

    echo [INFO] Activating virtual environment...
    call .venv\Scripts\activate.bat

    echo [INFO] Installing dependencies from requirements.txt...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo [SUCCESS] Dependencies installed.
    echo.
) else (
    echo [INFO] Virtual environment found. Activating...
    call .venv\Scripts\activate.bat
    echo [SUCCESS] Virtual environment activated.
    echo.
)

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found. Copying from .env.example...
    copy .env.example .env >nul
    echo [INFO] Please edit .env to customize your API key.
    echo.
)

REM Display current settings
echo [INFO] Starting server with settings:
echo        - Host: 0.0.0.0
echo        - Port: 8000
echo        - Reload: Enabled
echo.
echo [INFO] Server will be available at: http://localhost:8000
echo [INFO] API Documentation at: http://localhost:8000/docs
echo [INFO] Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

REM Start the FastAPI server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

REM If server exits, pause so user can see any error messages
if errorlevel 1 (
    echo.
    echo [ERROR] Server exited with an error.
    pause
)
