@echo off
chcp 65001 >nul
title CRT - Leallitas

echo  CRT Ajanlatseged leallitasa...

:: WSL2 mod
wsl -d CRT -- echo "" >nul 2>&1
if %errorLevel% equ 0 (
    wsl -d CRT -- bash -c "bash '%~dp0_setup/wsl_stop.sh'" 2>nul
    echo  WSL2 szolgaltatasok leallitva.
    goto :end
)

:: Natív mod (fallback)
taskkill /f /im python.exe >nul 2>&1
if exist "%~dp0db\pgsql16\bin\pg_ctl.exe" (
    "%~dp0db\pgsql16\bin\pg_ctl.exe" stop -D "%~dp0db\data" -m fast >nul 2>&1
)
echo  Natív szolgaltatasok leallitva.

:end
echo  Kesz.
timeout /t 2 /nobreak >nul
