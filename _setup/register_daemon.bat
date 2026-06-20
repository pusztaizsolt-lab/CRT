@echo off
chcp 65001 >nul
:: ================================================================
:: CRT Daemon – Windows Service regisztráció NSSM-mel
:: Futtatás: jobb klikk → Futtatás rendszergazdaként
:: NSSM letöltés: https://nssm.cc/download
:: ================================================================
setlocal

set CRT_ROOT=D:\CRT
set NSSM=nssm.exe
set SERVICE=CRT-Daemon
set PYTHON=py
set PYTHON_ARGS=-3.11 %CRT_ROOT%\crt_daemon.py

echo.
echo  CRT Daemon – Service regisztráció
echo  ===================================

:: NSSM ellenőrzés
where %NSSM% >nul 2>&1
if errorlevel 1 (
    echo  [HIBA] nssm.exe nem található a PATH-ban.
    echo         Tedd a nssm.exe-t a C:\Windows\System32\ mappába,
    echo         vagy add hozzá a PATH-hoz.
    echo         Letöltés: https://nssm.cc/download
    pause
    exit /b 1
)

:: Meglévő service eltávolítása ha van
sc query %SERVICE% >nul 2>&1
if not errorlevel 1 (
    echo  Meglévő service leállítása és eltávolítása...
    %NSSM% stop %SERVICE% >nul 2>&1
    %NSSM% remove %SERVICE% confirm >nul 2>&1
)

:: Service telepítése
echo  Service telepítése: %SERVICE%
%NSSM% install %SERVICE% %PYTHON% %PYTHON_ARGS%
if errorlevel 1 (
    echo  [HIBA] Service telepítés sikertelen.
    pause
    exit /b 1
)

:: Beállítások
%NSSM% set %SERVICE% DisplayName    "CRT Daemon – Felügyelő"
%NSSM% set %SERVICE% Description    "CRT Ajánlatsegéd háttérszolgáltatás és watchdog (:8099)"
%NSSM% set %SERVICE% Start          SERVICE_AUTO_START
%NSSM% set %SERVICE% AppDirectory   %CRT_ROOT%
%NSSM% set %SERVICE% AppStdout      %CRT_ROOT%\logs\daemon_service.log
%NSSM% set %SERVICE% AppStderr      %CRT_ROOT%\logs\daemon_service_err.log
%NSSM% set %SERVICE% AppRotateFiles 1
%NSSM% set %SERVICE% AppRotateBytes 5242880

:: Indítás
echo  Service indítása...
%NSSM% start %SERVICE%
if errorlevel 1 (
    echo  [FIGYELEM] Service elindítása sikertelen – kézzel: nssm start %SERVICE%
) else (
    echo  [OK] CRT Daemon fut Windows Service-ként.
    echo       http://localhost:8099
)

echo.
echo  Kezelés:
echo    nssm start   %SERVICE%
echo    nssm stop    %SERVICE%
echo    nssm restart %SERVICE%
echo    nssm remove  %SERVICE% confirm
echo.
pause
