@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo SafeVault -- Automatic Backup & Restore
echo Starting SafeVault Desktop Application...
echo =======================================================

:: Try py launcher first, then python
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set PYTHON_CMD=py
    goto :check_deps
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set PYTHON_CMD=python
    goto :check_deps
)

echo [ERROR] Neither 'py' nor 'python' was found in PATH.
echo Please install Python 3.11 or newer and ensure it is added to your PATH.
echo Press any key to exit...
pause >nul
exit /b 1

:check_deps
echo Using Python command: %PYTHON_CMD%
%PYTHON_CMD% -c "import customtkinter" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Installing required dependencies...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo [INFO] Launching SafeVault GUI...
%PYTHON_CMD% main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application exited with error code %ERRORLEVEL%.
    pause
)
