@echo off
chcp 65001 >nul
setlocal
set BASEDIR=%~dp0
cd /d "%BASEDIR%"

echo.
echo  ================================================
echo   CRT Ajanlatseged -- Elso telepites / Setup
echo   %BASEDIR%
echo  ================================================
echo.

:: Python 3.11 ellenorzese
py -3.11 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HIBA] Python 3.11 nem talalhato!
    echo        Telepitsd: https://www.python.org/downloads/release/python-3119/
    pause & exit /b 1
)
echo [OK] Python 3.11 megvan.

:: venv letrehozasa ha nincs
if not exist "%BASEDIR%venv\Scripts\python.exe" (
    echo [1/3] Python venv letrehozasa...
    py -3.11 -m venv "%BASEDIR%venv"
    if %errorlevel% neq 0 ( echo HIBA: venv letrehozas sikertelen! & pause & exit /b 1 )
    echo [OK] venv letrehozva.
) else (
    echo [OK] venv mar megvan.
)

:: csomagok telepitese
echo [2/3] Python csomagok telepitese (ez par percig tarthat)...
set PATH=%BASEDIR%db\pgsql16\bin;%PATH%
set PYTHONUTF8=1
"%BASEDIR%venv\Scripts\pip.exe" install -r "%BASEDIR%requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo HIBA: pip install sikertelen!
    pause & exit /b 1
)
echo [OK] Python csomagok telepitve.

:: Playwright chromium
echo [3/3] Playwright Chromium telepitese (web scraper)...
"%BASEDIR%venv\Scripts\python.exe" -m playwright install chromium
echo [OK] Playwright kesz.

echo.
echo  ================================================
echo   Setup kesz! Kovetkezo lepes: INDITAS.bat
echo  ================================================
pause
