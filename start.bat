@echo off
chcp 65001 >nul
cd /d "%~dp0"
title CRT Ajánlatsegéd

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     CRT Ajánlatsegéd – Indítás          ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── WSL2 mód (ha telepítve) ───────────────────────────────
wsl -d CRT -- echo "" >nul 2>&1
if %errorLevel% equ 0 (
    echo  [WSL2 mód] Szolgáltatások indítása...
    start /b wsl -d CRT -- bash -c "bash '%~dp0_setup/wsl_start.sh'" 2>nul
    echo  Várakozás a szerverre...
    :wsl_wait
    timeout /t 2 /nobreak >nul
    curl -sf http://localhost:8000/health >nul 2>&1
    if %errorLevel% neq 0 goto wsl_wait
    echo  Szerver kész.
    start "" "http://localhost/login.html"
    goto :end
)

:: ── Windows natív mód (fallback) ──────────────────────────
echo  [Natív mód] Szolgáltatások indítása...

echo  [1/3] PostgreSQL...
if exist "db\pgsql\bin\pg_ctl.exe" (
    "db\pgsql\bin\pg_ctl.exe" status -D "db_data\pg" >nul 2>&1
    if %errorLevel% neq 0 (
        "db\pgsql\bin\pg_ctl.exe" start -D "db_data\pg" -l "logs\pg.log" -w
    )
    echo         OK
) else (
    echo         KIHAGYVA (PostgreSQL nincs natív módban)
)

echo  [2/3] Backend...
start "CRT Backend" /min cmd /c "py -3.11 -m uvicorn main:app --host 0.0.0.0 --port 8000 >> logs\backend\backend.log 2>&1"
timeout /t 4 /nobreak >nul
echo         OK

echo  [3/3] Böngésző megnyitása...
start "" "ui\login.html"
echo         OK

:end
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  UI:      http://localhost              ║
echo  ║  API:     http://localhost:8000         ║
echo  ║  Docs:    http://localhost:8000/docs    ║
echo  ╚══════════════════════════════════════════╝
echo.
