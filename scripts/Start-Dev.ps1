#Requires -Version 5.1
<#
.SYNOPSIS
  Start FastAPI backend and Angular dev server in separate PowerShell windows.

.NOTES
  If Windows blocks this file (not digitally signed), run:
    powershell -ExecutionPolicy Bypass -File .\scripts\Start-Dev.ps1
  Or once per user:
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
  $example = Join-Path $Root ".env.example"
  if (Test-Path $example) {
    Copy-Item $example $envFile
    Write-Host "Created .env from .env.example" -ForegroundColor Yellow
  } else {
    Write-Host "Warning: .env missing and .env.example not found." -ForegroundColor Yellow
  }
}

$venvPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  throw "Virtual environment missing. Run: powershell -ExecutionPolicy Bypass -File .\scripts\Setup-Dev.ps1"
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
