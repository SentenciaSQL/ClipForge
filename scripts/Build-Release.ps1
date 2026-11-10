#Requires -Version 5.1
<#
.SYNOPSIS
  Build Angular frontend, optional PyInstaller backend sidecar, and Tauri Windows installer.
#>
param(
  [switch]$SkipSidecar,
  [switch]$SkipTauri
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Angular = Join-Path $Root "desktop\angular-app"
$Backend = Join-Path $Root "backend"
$SidecarDir = Join-Path $Angular "src-tauri\sidecars"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"

Write-Host "==> Building Angular production bundle" -ForegroundColor Cyan
Push-Location $Angular
npm ci
npx ng build --configuration=production
Pop-Location

if (-not $SkipSidecar) {
  Write-Host "==> Building backend sidecar with PyInstaller" -ForegroundColor Cyan
  if (-not (Test-Path $VenvPython)) {
    throw "Missing backend venv. Run .\scripts\Setup-Dev.ps1 first."
  }
  & $VenvPython -m pip install --upgrade pyinstaller
  New-Item -ItemType Directory -Force -Path $SidecarDir | Out-Null
  Push-Location $Backend
  & $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name ai-video-clipper-api `
    --paths . `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.loops `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols `
    --hidden-import uvicorn.protocols.http `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan `
    --hidden-import uvicorn.lifespan.on `
    main.py
  Copy-Item ".\dist\ai-video-clipper-api.exe" (Join-Path $SidecarDir "ai-video-clipper-api.exe") -Force
  # Also copy extensionless name for resource lookup on some hosts
  Copy-Item ".\dist\ai-video-clipper-api.exe" (Join-Path $SidecarDir "ai-video-clipper-api") -Force
  Pop-Location
  Write-Host "Sidecar copied to $SidecarDir" -ForegroundColor Green
}

if (-not $SkipTauri) {
  Write-Host "==> Building Tauri Windows bundles (NSIS/MSI)" -ForegroundColor Cyan
  Push-Location $Angular
  npm run tauri -- build
  Pop-Location
  Write-Host "Installer artifacts under desktop\angular-app\src-tauri\target\release\bundle\" -ForegroundColor Green
}

Write-Host "Build-Release complete." -ForegroundColor Green
