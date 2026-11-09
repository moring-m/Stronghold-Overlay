@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\installed.ok (
  echo [1/2] Creating virtual environment...
  python -m venv .venv || (echo Python not found. Install Python 3.10+ and check "Add python.exe to PATH". & pause & exit /b 1)
  echo [2/2] Installing packages... (first run only)
  .venv\Scripts\python -m pip install -r requirements.txt || (pause & exit /b 1)
  echo ok> .venv\installed.ok
)
.venv\Scripts\python -m stronghold_overlay
if errorlevel 1 pause
