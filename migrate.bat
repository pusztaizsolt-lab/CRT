@echo off
chcp 65001 >nul
setlocal
set BASEDIR=%~dp0
set PYTHON=%BASEDIR%venv\Scripts\python.exe
cd /d "%BASEDIR%"

echo ================================================
echo  CRT -- Adatbazis migraciok futtatasa
echo  Mappa: %BASEDIR%
echo ================================================

if not exist "%PYTHON%" (
    echo HIBA: venv nem talalhato! Futtasd elobb: setup.bat
    pause & exit /b 1
)

set PYTHONUTF8=1

echo [0/7] Alap tablak letrehozasa (db_schema.py)...
"%PYTHON%" db_schema.py
if %errorlevel% neq 0 (
    echo HIBA: db_schema.py sikertelen!
    pause & exit /b 1
)

echo.
echo [1/7] Admin felhasznalo letrehozasa (v04 elott kell!)...
"%PYTHON%" _setup\create_admin.py
if %errorlevel% neq 0 (
    echo HIBA: admin letrehozas sikertelen!
    pause & exit /b 1
)

echo [2/7] v02 migracio (cikktorzs)...
"%PYTHON%" db_migrate_v02.py
echo [3/7] v04 migracio (auth)...
"%PYTHON%" db_migrate_v04.py
echo [4/7] v05 migracio (quotes, web)...
"%PYTHON%" db_migrate_v05.py
echo [5/7] v06 migracio (indexek)...
"%PYTHON%" db_migrate_v06.py
echo [6/7] v07 migracio (Ollama, ChromaDB)...
"%PYTHON%" db_migrate_v07.py
echo [7/7] v08 migracio (LoRA)...
"%PYTHON%" db_migrate_v08.py

echo.
echo ================================================
echo  DB kesz! Kovetkezo lepes: start_backend.bat
echo ================================================
pause
