@echo off
chcp 65001 >nul
setlocal
set BASEDIR=%~dp0
set PYTHON=%BASEDIR%venv\Scripts\python.exe
set PGDATA=%BASEDIR%db\data
cd /d "%BASEDIR%"

echo.
echo  ================================================
echo   CRT Ajanlatseged -- Teljes inditas
echo   %BASEDIR%
echo  ================================================
echo.

:: 1. venv ellenorzese
if not exist "%PYTHON%" (
    echo [HIBA] A venv meg nincs letrehozva.
    echo        Futtasd elobb: setup.bat
    pause & exit /b 1
)
echo [OK] Python venv: %PYTHON%

:: 2. PostgreSQL -- elso inditasnal init
if not exist "%PGDATA%\PG_VERSION" (
    echo [INIT] Elso inditas -- adatbazis letrehozasa...
    call "%BASEDIR%db_init.bat"
    if %errorlevel% neq 0 ( pause & exit /b 1 )
    echo [INIT] Migraciok futtatasa...
    call "%BASEDIR%migrate.bat"
    if %errorlevel% neq 0 ( pause & exit /b 1 )
) else (
    echo [OK] Adatbazis mar inicializalva.
    call "%BASEDIR%db_start.bat"
    if %errorlevel% neq 0 ( pause & exit /b 1 )
)

:: 3. Backend inditas
echo.
echo [START] FastAPI backend inditasa...
echo         http://localhost:8000
echo         ui\login.html
echo.
"%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
