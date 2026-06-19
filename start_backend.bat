@echo off
chcp 65001 >nul
setlocal
set BASEDIR=%~dp0
set PYTHON=%BASEDIR%venv\Scripts\python.exe
cd /d "%BASEDIR%"

echo ================================================
echo  CRT Ajanlatseged -- Backend inditas
echo  Mappa: %BASEDIR%
echo ================================================

if not exist "%PYTHON%" (
    echo HIBA: venv nem talalhato! Futtasd elobb: setup.bat
    pause & exit /b 1
)

echo PostgreSQL ellenorzese...
call "%BASEDIR%db_start.bat"
if %errorlevel% neq 0 ( pause & exit /b 1 )

echo.
echo FastAPI szerver inditasa...
echo  Megnyithato: ui\login.html
echo  API docs:    http://localhost:8000/docs
echo  Leallitas:   Ctrl+C
echo.
"%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
