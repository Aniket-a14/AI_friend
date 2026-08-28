# ==============================================================================
#  AI Friend — Automated Windows PowerShell Installer
#  Usage:
#    irm https://raw.githubusercontent.com/Aniket-a14/AI_friend/main/scripts/install.ps1 | iex
# ==============================================================================

[CmdletBinding()]
param (
    [string]$TargetDir = "$HOME\AI_friend",
    [switch]$NoStart,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Banner {
    Write-Host @"
      _    ___   _____ ____  ___ _____ _   _ ____  
     / \  |_ _| |  ___|  _ \|_ _| ____| \ | |  _ \ 
    / _ \  | |  | |_  | |_) || ||  _| |  \| | | | |
   / ___ \ | |  |  _| |  _ < | || |___| |\  | |_| |
  /_/   \_\___| |_|   |_| \_\___|_____|_| \_|____/ 
"@ -ForegroundColor Cyan
    Write-Host "  An embodied, local-first lifelong companion on your own hardware.`n" -ForegroundColor DarkGray
}

Write-Banner

Write-Host "==> Platform: Windows (PowerShell / Docker Desktop)" -ForegroundColor Cyan

# 1. Prerequisite Validation
Write-Host "==> Checking prerequisites..." -ForegroundColor Cyan

# Check Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warning "Git is not installed. Attempting to install via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Git.Git -e --source winget
    } else {
        Write-Error "Please install Git from https://git-scm.com/download/win and re-run."
        return
    }
}
Write-Host "[OK] Git is available" -ForegroundColor Green

# Check Python
$pythonCmd = $null
foreach ($cmd in @("python3.13", "python3.12", "python3.11", "python", "py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd
        break
    }
}

if (-not $pythonCmd) {
    Write-Warning "Python 3.11+ not found. Attempting to install via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Python.Python.3.12 -e --source winget
        $pythonCmd = "python"
    } else {
        Write-Error "Please install Python 3.11+ from https://python.org and add to PATH."
        return
    }
}
Write-Host "[OK] Python is available ($pythonCmd)" -ForegroundColor Green

# Check Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Warning "Docker Desktop is required to run the 9-agent signal mesh."
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
}

# Check Ollama
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Warning "Ollama is recommended for local LLM inference."
    Write-Host "Download Ollama for Windows: https://ollama.com/download/windows" -ForegroundColor Yellow
}

if ($DryRun) {
    Write-Host "`n[OK] Dry run complete! System meets Windows prerequisites." -ForegroundColor Green
    return
}

# 2. Clone or Update Repo
$repoUrl = "https://github.com/Aniket-a14/AI_friend.git"
if (Test-Path "$TargetDir\.git") {
    Write-Host "==> Existing checkout found at $TargetDir. Pulling latest..." -ForegroundColor Cyan
    Set-Location $TargetDir
    git pull --ff-only
} else {
    Write-Host "==> Cloning AI Friend into $TargetDir..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path (Split-Path $TargetDir) | Out-Null
    git clone $repoUrl $TargetDir
    Set-Location $TargetDir
}

# 3. Environment & Python Setup
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] Created .env configuration file" -ForegroundColor Green
}

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating Python virtual environment..." -ForegroundColor Cyan
    & $pythonCmd -m venv .venv
}

Write-Host "==> Installing Python dependencies..." -ForegroundColor Cyan
& ".\.venv\Scripts\pip.exe" install --upgrade pip | Out-Null
if (Test-Path "backend\pyproject.toml") {
    & ".\.venv\Scripts\pip.exe" install -e backend | Out-Null
}

# 4. Provision default voice
& ".\.venv\Scripts\python.exe" backend\scripts\bootstrap\ensure_default_voice_sample.py

# 5. Summary & Launcher
Write-Host @"

═════════════════════════════════════════════════════════════════
             AI FRIEND INSTALLATION COMPLETE!                    
═════════════════════════════════════════════════════════════════
Location:  $TargetDir
Commands:
  .\start.bat                Start the complete system
  .\start.ps1                PowerShell launcher
  python -m scripts.friend_cli talk   Terminal conversation
─────────────────────────────────────────────────────────────────
"@ -ForegroundColor Green

if (-not $NoStart) {
    $startNow = Read-Host "Would you like to launch AI Friend now? (Y/n)"
    if ($startNow -eq "" -or $startNow -match "^[Yy]") {
        & ".\start.ps1"
    }
}
