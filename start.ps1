# ==============================================================================
#  AI Friend — Windows PowerShell Mesh Launcher
#  Usage: .\start.ps1 [-Mode full|light|heavy] [-Vision]
# ==============================================================================

[CmdletBinding()]
param (
    [ValidateSet("full", "light", "heavy")]
    [string]$Mode = "full",
    [switch]$Vision
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

Write-Host "==> Starting AI Friend on Windows (Mode: $Mode)" -ForegroundColor Cyan

# 1. Check .env
if (-not (Test-Path ".env")) {
    Write-Error ".env not found at repo root. Copy .env.example to .env first."
    exit 1
}

# 2. Check Docker Desktop
try {
    docker info | Out-Null
} catch {
    Write-Error "Docker Desktop is not running. Please start Docker Desktop and try again."
    exit 1
}

# 3. Create ai_mesh_network
try {
    docker network inspect ai_mesh_network | Out-Null
} catch {
    Write-Host "==> Creating ai_mesh_network" -ForegroundColor Cyan
    docker network create ai_mesh_network | Out-Null
}

# 4. Check Ollama
$OllamaUrl = "http://127.0.0.1:11434"
try {
    $resp = Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -Method Get -TimeoutSec 3
    Write-Host "[OK] Ollama is connected" -ForegroundColor Green
} catch {
    Write-Warning "Ollama is not reachable at $OllamaUrl. Please start Ollama or run 'ollama serve'."
}

# 5. Bring up infra
$infraServices = @("postgres", "neo4j", "redis", "nats")
if ($Mode -eq "full") {
    $infraServices += "livekit"
}

Write-Host "==> Bringing up infrastructure containers..." -ForegroundColor Cyan
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d $infraServices

# 6. Wait for Postgres
Write-Host "==> Waiting for Postgres to become healthy..." -ForegroundColor Cyan
$postgresReady = $false
for ($i = 0; $i -lt 30; $i++) {
    $status = (docker inspect --format='{{.State.Health.Status}}' postgres_db 2>$null)
    if ($status -eq "healthy") {
        $postgresReady = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $postgresReady) {
    Write-Warning "Postgres is still initializing; proceeding with launch."
}

# 7. Start Mesh Layer
$composeFiles = @("-f", "docker-compose.infra.yml", "-f", "docker-compose.prod.yml")
if ($Mode -eq "light") { $composeFiles += @("-f", "docker-compose.light.yml") }
if ($Mode -eq "heavy") { $composeFiles += @("-f", "docker-compose.heavy.yml") }

$upArgs = @("up", "-d", "--build")
if ($Vision) {
    $upArgs = @("--profile", "vision") + $upArgs
}

Write-Host "==> Starting AI Friend 9-agent cognitive mesh..." -ForegroundColor Cyan
docker compose @composeFiles @upArgs

Write-Host "`n[OK] AI Friend mesh is up! Check status with: docker compose ps" -ForegroundColor Green
Write-Host "Web UI available at: http://localhost:3000" -ForegroundColor Cyan
