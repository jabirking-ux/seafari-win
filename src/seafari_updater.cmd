@echo off
setlocal EnableDelayedExpansion
set "ACTION=%~1"
set "ARG2=%~2"
set "TARGET_PID=%~3"
set "TARGET_DIR=%~4"

if "%TARGET_DIR%"=="" set "TARGET_DIR=%~dp0"
if "%TARGET_DIR:~-1%"=="\" set "TARGET_DIR=%TARGET_DIR:~0,-1%"

set "INSTALLER=%ARG2%"

if /i "%ACTION%"=="--download-and-apply" (
    set "DOWNLOAD_URL=%ARG2%"
    set "INSTALLER=%TEMP%\seafari_update_%RANDOM%.exe"
    curl -fL --retry 3 -o "!INSTALLER!" "!DOWNLOAD_URL!"
)

if not "%TARGET_PID%"=="" (
    :wait_loop
    tasklist /fi "PID eq %TARGET_PID%" 2>nul | findstr /i "%TARGET_PID%" >nul
    if not errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto wait_loop
    )
)
timeout /t 1 /nobreak >nul

if exist "%INSTALLER%" (
    start /wait "" "%INSTALLER%" /S /D=%TARGET_DIR%
    del /f /q "%INSTALLER%" >nul 2>&1
)

start "" "%TARGET_DIR%\seafari.exe"
exit
