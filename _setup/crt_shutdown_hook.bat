@echo off
chcp 65001 >nul
echo %DATE% %TIME% CRT auto-stop (shutdown hook) >> D:\CRT\logs\shutdown.log 2>&1
call D:\CRT\stop.bat >> D:\CRT\logs\shutdown.log 2>&1
echo %DATE% %TIME% CRT leallitva. >> D:\CRT\logs\shutdown.log 2>&1
