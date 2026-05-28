@echo off
cd /d "%~dp0"
title CRT Ajanlatseged

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   CRT Ajanlatseged - Inditas...      ║
echo  ╚══════════════════════════════════════╝
echo.

:: ── 1. PostgreSQL ────────────────────────────────────────
echo  [1/3] PostgreSQL ellenorzese...
"db\pgsql\bin\pg_ctl.exe" status -D "db_data" > nul 2>&1
if %errorlevel%==0 (
    echo  OK  PostgreSQL mar fut
) else (
    echo  ... PostgreSQL indul...
    "db\pgsql\bin\pg_ctl.exe" start -D "db_data" -l "pg.log" -w
    timeout /t 3 /nobreak > nul
    echo  OK  PostgreSQL elinditva
)
echo.

:: ── 2. Backend ───────────────────────────────────────────
echo  [2/3] Backend indul...
start "CRT Backend" /min cmd /c "py -3.11 -m uvicorn main:app --host 0.0.0.0 --port 8000 >> crt.log 2>&1"
echo  ... Varakozas a szerverre...
timeout /t 4 /nobreak > nul
echo.

:: ── 3. Kezelopult megnyitasa ─────────────────────────────
echo  [3/3] Kezelopult megnyitasa...
start "" "ui\kezelőpult.html"
echo.

echo  ╔══════════════════════════════════════╗
echo  ║   Rendszer fut!                      ║
echo  ║   API:  http://localhost:8000        ║
echo  ║   Docs: http://localhost:8000/docs   ║
echo  ╚══════════════════════════════════════╝
echo.
echo  Bezarashoz nyomj egy billentyut...
pause > nul
