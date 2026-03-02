@echo off
chcp 65001 >nul 2>&1
title Jarvis - Autonomous AI Assistant

echo.
echo  ======================================================
echo     JARVIS - Autonomous AI Assistant
echo  ======================================================
echo.

:: ─── Locate project directory ──────────────────────
cd /d "%~dp0"

:: ─── Check for Python ──────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found in PATH.
    echo  Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: ─── Check for .env ────────────────────────────────
if not exist ".env" (
    echo  [WARN] No .env file found.
    echo  Copying .env.example to .env ...
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo  [INFO] .env created. Edit it with your API keys.
        start notepad ".env"
        pause
        exit /b 0
    ) else (
        echo  [WARN] No .env.example found. Continuing with defaults...
    )
)

:: ─── Activate venv if present ──────────────────────
if exist ".venv\Scripts\activate.bat" (
    echo  [*] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo  [WARN] No .venv found. Running with system Python.
    echo  Tip: python -m venv .venv ^& .venv\Scripts\activate ^& pip install -r Jarvis\requirements.txt
)

:: ─── Check dependencies ───────────────────────────
python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [*] Installing dependencies...
    pip install -r Jarvis\requirements.txt
    if %errorlevel% neq 0 (
        echo  [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
)

:: ─── Install colorama if missing ───────────────────
python -c "import colorama" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [*] Installing colorama for colored output...
    pip install colorama >nul 2>&1
)

:: ─── Launch Jarvis ─────────────────────────────────
echo.
echo  [*] Starting Jarvis...
echo  --------------------------------------------------
echo.
python -m Jarvis.main

:: ─── Exit ──────────────────────────────────────────
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Jarvis exited with error code %errorlevel%
    echo  Check Jarvis\logs\crash.log for details.
)
echo.
pause
