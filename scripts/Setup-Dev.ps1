#Requires -Version 5.1
<#
.SYNOPSIS
  Create Python venv, install backend + frontend dependencies.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== AI Video Clipper — Dev Setup ===" -ForegroundColor Cyan

if (-not (Test-Path "$Root\.env")) {
  Copy-Item "$Root\.env.example" "$Root\.env"
  Write-Host "Created .env from .env.example"
}

# Prefer Python 3.12
$python = $null
foreach ($candidate in @("py -3.12", "python3.12", "python")) {
  try {
    $ver = Invoke-Expression "$candidate --version" 2>&1 | Out-String
    if ($ver -match "3\.12") {
      $python = $candidate
      break
    }
    if (-not $python) { $python = $candidate }
  } catch {}
}

if (-not $python) {
  throw "Python 3.12 not found. Install Python 3.12 and re-run."
}

Write-Host "Using: $python"

$venvPath = Join-Path $Root "backend\.venv"
if (-not (Test-Path $venvPath)) {
  Invoke-Expression "$python -m venv `"$venvPath`""
}

$pip = Join-Path $venvPath "Scripts\pip.exe"
$py = Join-Path $venvPath "Scripts\python.exe"

& $py -m pip install --upgrade pip
# Core API first, then full AI/media stack (Whisper/OpenCV/etc.)
& $pip install -r (Join-Path $Root "backend\requirements-core.txt")
& $pip install -r (Join-Path $Root "backend\requirements.txt")

Write-Host "Installing Angular dependencies..." -ForegroundColor Cyan
Push-Location (Join-Path $Root "desktop\angular-app")
npm install
Pop-Location

Write-Host "Creating workspace folders..." -ForegroundColor Cyan
@(
  "workspace\originals",
  "workspace\projects",
  "workspace\temporary",
  "workspace\exports"
) | ForEach-Object {
  New-Item -ItemType Directory -Force -Path (Join-Path $Root $_) | Out-Null
}

Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next: .\scripts\Start-Dev.ps1"
