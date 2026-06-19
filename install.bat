@echo off
chcp 65001 >nul
title CRT Ajánlatsegéd – Telepítő

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║       CRT Ajánlatsegéd – Telepítő v0.6              ║
echo  ║       Civil Rendszertechnika Kft.                    ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Admin jogosultság ellenőrzése
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo  [!] Adminisztrátori jog szükséges.
    echo      Kattints jobb gombbal az install.bat-ra, majd:
    echo      "Futtatás rendszergazdaként"
    pause
    exit /b 1
)

:: PowerShell verziót ellenőrzünk
powershell -Command "if ($PSVersionTable.PSVersion.Major -lt 5) { exit 1 }"
if %errorLevel% neq 0 (
    echo  [!] PowerShell 5+ szükséges. Windows 10/11-en alapértelmezett.
    pause
    exit /b 1
)

:: Telepítő indítása
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_setup\CRT_install.ps1" -InstallDir "%~dp0"
