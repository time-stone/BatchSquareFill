@echo off
chcp 65001 >nul

cd /d "%~dp0"
echo #########################################
echo [OK] SWITCHING TO FOLDER OF SCRIPT-File: %CD%

echo #################################################################################
echo [??] CHECKING if UV Package Manager is installed...
where uv >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo [OK] uv is installed
) else (
    echo [!!] uv is not installed.
    echo Install via:  winget install astral-sh.uv
    echo   or visit:   https://astral.sh/uv
    echo EXITING...
    pause
    exit /b 1
)

echo #################################################################################
echo [..] SYNCING dependencies...
uv sync

echo #################################################################################
echo [>>] RUNNING BatchSquareFill.py...
.venv\Scripts\python.exe BatchSquareFill.py

echo #################################################################################
echo Press any key to close...
pause >nul
