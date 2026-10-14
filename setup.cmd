@echo off
rem Double-click this file to set up the LinkedIn Coach (Windows).
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set RC=%ERRORLEVEL%
if not defined CI pause
exit /b %RC%
