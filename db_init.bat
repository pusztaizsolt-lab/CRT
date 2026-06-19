@echo off
chcp 65001 >nul
setlocal
set BASEDIR=%~dp0
set PGDIR=%BASEDIR%db\pgsql16
set PGDATA=%BASEDIR%db\data
set PGLOG=%BASEDIR%logs\system\pg_init.log

echo ================================================
echo  CRT -- PostgreSQL inicializalas (elso inditas)
echo  Mappa: %BASEDIR%
echo ================================================

if not exist "%PGDIR%\bin\pg_ctl.exe" (
    echo HIBA: PostgreSQL nem talalhato: %PGDIR%
    pause & exit /b 1
)

if exist "%PGDATA%\PG_VERSION" (
    echo Az adatbazis cluster mar inicializalva van.
    goto :start
)

echo [1/3] Adatbazis cluster inicializalasa...
"%PGDIR%\bin\initdb.exe" -D "%PGDATA%" -U postgres -E UTF8 --locale=Hungarian_Hungary.1250 2>nul
if %errorlevel% neq 0 (
    "%PGDIR%\bin\initdb.exe" -D "%PGDATA%" -U postgres -E UTF8 --locale=C
)
if %errorlevel% neq 0 (
    echo HIBA: initdb sikertelen!
    pause & exit /b 1
)
echo OK: Cluster letrehozva.

:: postgresql.conf beallitas: port 5433, csak IPv4 localhost
echo port = 5433 >> "%PGDATA%\postgresql.conf"
echo listen_addresses = '127.0.0.1' >> "%PGDATA%\postgresql.conf"
echo OK: postgresql.conf frissitve (port 5433).

:start
echo [2/3] PostgreSQL szerver inditasa...
"%PGDIR%\bin\pg_ctl.exe" start -D "%PGDATA%" -l "%PGLOG%" -w
if %errorlevel% neq 0 (
    echo HIBA: PostgreSQL nem indult! Naplo: %PGLOG%
    pause & exit /b 1
)

echo [3/3] crt adatbazis es felhasznalo letrehozasa...
"%PGDIR%\bin\psql.exe" -U postgres -p 5433 -c "CREATE USER crt_user WITH PASSWORD 'crt2026';" 2>nul
"%PGDIR%\bin\psql.exe" -U postgres -p 5433 -c "CREATE DATABASE crt OWNER crt_user;" 2>nul
"%PGDIR%\bin\psql.exe" -U postgres -p 5433 -c "GRANT ALL PRIVILEGES ON DATABASE crt TO crt_user;" 2>nul
echo OK: Adatbazis kesz.

echo.
echo  Kovetkezo lepes: migrate.bat
pause
