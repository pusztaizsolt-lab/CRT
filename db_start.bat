@echo off
chcp 65001 >nul
setlocal
set BASEDIR=%~dp0
set PGDIR=%BASEDIR%db\pgsql16
set PGDATA=%BASEDIR%db\data
set PGLOG=%BASEDIR%logs\system\pg.log

if not exist "%PGDATA%\PG_VERSION" (
    echo HIBA: Adatbazis meg nincs inicializalva! Futtasd: db_init.bat
    pause & exit /b 1
)

"%PGDIR%\bin\pg_ctl.exe" status -D "%PGDATA%" >nul 2>&1
if %errorlevel% == 0 (
    echo PostgreSQL mar fut.
    exit /b 0
)

echo PostgreSQL inditasa...
"%PGDIR%\bin\pg_ctl.exe" start -D "%PGDATA%" -l "%PGLOG%" -w -s
if %errorlevel% neq 0 (
    echo HIBA: PostgreSQL nem indult! Naplo: %PGLOG%
    pause & exit /b 1
)
echo OK: PostgreSQL fut.
