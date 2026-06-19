@echo off
chcp 65001 >nul
title CRT – Státusz

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║       CRT Ajánlatsegéd – Státusz        ║
echo  ╚══════════════════════════════════════════╝
echo.

:: Backend
curl -sf http://localhost:8000/health >nul 2>&1
if %errorLevel% equ 0 (echo  Backend API:   ✓ FUT) else (echo  Backend API:   ✗ NEM FUT)

:: UI
curl -sf http://localhost/ >nul 2>&1
if %errorLevel% equ 0 (echo  Nginx UI:      ✓ FUT) else (echo  Nginx UI:      – nem elérhető)

:: Ollama
curl -sf http://localhost:11434/ >nul 2>&1
if %errorLevel% equ 0 (echo  Ollama LLM:    ✓ FUT) else (echo  Ollama LLM:    – nem elérhető)

:: ChromaDB
curl -sf http://localhost:8001/api/v1/heartbeat >nul 2>&1
if %errorLevel% equ 0 (echo  ChromaDB:      ✓ FUT) else (echo  ChromaDB:      – nem elérhető)

:: WSL
wsl -d CRT -- echo "" >nul 2>&1
if %errorLevel% equ 0 (echo  WSL2 CRT:      ✓ AKTÍV) else (echo  WSL2 CRT:      – nincs telepítve)

echo.
pause
