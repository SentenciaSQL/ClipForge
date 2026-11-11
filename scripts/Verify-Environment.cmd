@echo off
REM Avoids PowerShell ExecutionPolicy blocks on unsigned .ps1 scripts.
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Environment.ps1"
if errorlevel 1 pause
