#Requires -Version 5.1
<#
.SYNOPSIS
  Verify Windows development dependencies for AI Video Clipper.
#>
$ErrorActionPreference = "Continue"
Write-Host "=== AI Video Clipper — Environment Verification ===" -ForegroundColor Cyan

function Test-Cmd {
  param([string]$Name, [string]$Command)
  try {
    $output = Invoke-Expression $Command 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0 -or $output) {
      Write-Host "[OK] $Name" -ForegroundColor Green
      Write-Host ("      " + ($output.Trim() -split "`n" | Select-Object -First 1))
      return $true
    }
  } catch {}
  Write-Host "[MISSING] $Name" -ForegroundColor Red
  return $false
}

Test-Cmd "Python" "python --version"
Test-Cmd "pip" "python -m pip --version"
Test-Cmd "Node.js" "node --version"
Test-Cmd "npm" "npm --version"
Test-Cmd "Rustc" "rustc --version"
Test-Cmd "Cargo" "cargo --version"
Test-Cmd "FFmpeg" "ffmpeg -version"
Test-Cmd "FFprobe" "ffprobe -version"
Test-Cmd "Ollama" "ollama --version"

Write-Host ""
Write-Host "NVIDIA / CUDA:" -ForegroundColor Cyan
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
  Write-Host "[OK] nvidia-smi" -ForegroundColor Green
} else {
  Write-Host "[MISSING] nvidia-smi (CPU fallback will be used)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Ollama models (if server running):" -ForegroundColor Cyan
try {
  ollama list
} catch {
  Write-Host "Ollama list unavailable" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Verification finished." -ForegroundColor Cyan
