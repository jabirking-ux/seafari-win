@echo off
setlocal
echo ========================================================
echo   Seafari for Windows - Build & Patch Pipeline
echo ========================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3 was not found in PATH. Please install Python 3.
    pause
    exit /b 1
)

if "%~1"=="" (
    set "TARGET_DIR=%LOCALAPPDATA%\Programs\Seafari"
) else (
    set "TARGET_DIR=%~1"
)

set "UBLOCK_XPI=%TARGET_DIR%\distribution\extensions\uBlock0@raymondhill.net.xpi"
set "ATBC_XPI=%TARGET_DIR%\distribution\extensions\ATBC@EasonWong.xpi"

python "%~dp0scripts\patch_windows_firefox.py" --firefox-dir "%TARGET_DIR%" --ublock-xpi "%UBLOCK_XPI%" --atbc-xpi "%ATBC_XPI%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build encountered an error.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [SUCCESS] Seafari for Windows patched successfully!
