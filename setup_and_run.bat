@echo off
title MealMatrix Backend Setup
color 0A
echo.
echo  ================================================
echo    MealMatrix Backend - Windows Setup + Run
echo  ================================================
echo.

:: ── Check Python ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo  [1/4] Python found:
python --version
echo.

:: ── Install dependencies ───────────────────────────────────────────────────────
echo  [2/4] Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo  Dependencies installed successfully.
echo.

:: ── Create required folders ────────────────────────────────────────────────────
echo  [3/4] Creating required folders...
if not exist "instance"      mkdir instance
if not exist "flask_session" mkdir flask_session
echo  Folders ready.
echo.

:: ── Start Flask ────────────────────────────────────────────────────────────────
echo  [4/4] Starting Flask backend...
echo.
echo  ================================================
echo    Server running at: http://127.0.0.1:5000
echo    Open THIS URL in your browser!
echo    Press Ctrl+C to stop the server.
echo  ================================================
echo.
python app.py

pause
