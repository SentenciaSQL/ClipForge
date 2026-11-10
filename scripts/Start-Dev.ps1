#Requires -Version 5.1
<#
.SYNOPSIS
  Start FastAPI backend and Angular dev server in separate PowerShell windows.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

$venvPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  throw "Virtual environment missing. Run .\scripts\Setup-Dev.ps1 first."
}

$backendCmd = @"
Set-Location '$Root\backend'
& '$venvPython' main.py
"@

$frontendCmd = @"
Set-Location '$Root\desktop\angular-app'
npm start
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host "Started backend (http://127.0.0.1:8000) and Angular (http://127.0.0.1:4200)." -ForegroundColor Green
Write-Host "API docs: http://127.0.0.1:8000/docs"
