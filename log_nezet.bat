@echo off
chcp 65001 >nul
setlocal
set BASEDIR=%~dp0

echo.
echo  ============================================
echo   CRT -- Naplo nezeto
echo  ============================================
echo.
echo  [1] Backend naplo (legfrissebb 50 sor)
echo  [2] PostgreSQL naplo
echo  [3] Rendszer / startup naplo
echo  [4] Osszes naplo (egyben)
echo  [5] Kilepes
echo.
set /p VALASZ=Valassz (1-5):

if "%VALASZ%"=="1" goto :backend
if "%VALASZ%"=="2" goto :postgres
if "%VALASZ%"=="3" goto :system
if "%VALASZ%"=="4" goto :osszes
if "%VALASZ%"=="5" goto :vege
goto :vege

:backend
echo.
echo  === Backend naplo (%BASEDIR%logs\backend\backend.log) ===
echo.
if exist "%BASEDIR%logs\backend\backend.log" (
    powershell -Command "Get-Content '%BASEDIR%logs\backend\backend.log' -Tail 50"
) else (
    echo  [URES] Backend naplo meg nem letezik.
)
echo.
pause & goto :vege

:postgres
echo.
echo  === PostgreSQL naplo (%BASEDIR%logs\system\pg.log) ===
echo.
if exist "%BASEDIR%logs\system\pg.log" (
    powershell -Command "Get-Content '%BASEDIR%logs\system\pg.log' -Tail 50"
) else (
    echo  [URES] PostgreSQL naplo meg nem letezik.
)
echo.
pause & goto :vege

:system
echo.
echo  === Rendszer naplo (%BASEDIR%logs\system\startup.log) ===
echo.
if exist "%BASEDIR%logs\system\startup.log" (
    powershell -Command "Get-Content '%BASEDIR%logs\system\startup.log' -Tail 50"
) else (
    echo  [URES] Startup naplo meg nem letezik.
)
echo.
pause & goto :vege

:osszes
echo.
echo  === Backend naplo ===
powershell -Command "if (Test-Path '%BASEDIR%logs\backend\backend.log') { Get-Content '%BASEDIR%logs\backend\backend.log' -Tail 30 } else { Write-Host '[ures]' }"
echo.
echo  === PostgreSQL naplo ===
powershell -Command "if (Test-Path '%BASEDIR%logs\system\pg.log') { Get-Content '%BASEDIR%logs\system\pg.log' -Tail 20 } else { Write-Host '[ures]' }"
echo.
echo  === Startup naplo ===
powershell -Command "if (Test-Path '%BASEDIR%logs\system\startup.log') { Get-Content '%BASEDIR%logs\system\startup.log' -Tail 20 } else { Write-Host '[ures]' }"
echo.
pause

:vege
