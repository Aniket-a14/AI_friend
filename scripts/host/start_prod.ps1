# Start AI Friend in PRODUCTION Mode
# Usage: ./scripts/start_prod.ps1

$ErrorActionPreference = "Stop"

Write-Host "🚀 Launching AI Friend (Production Mesh)..."

# 1. Ensure .env exists
if (-not (Test-Path ".env")) {
    Write-Error "❌ .env file missing! Please create one from .env.example"
    exit 1
}

# 2. Launch infrastructure first and wait for readiness.
# This ensures the external mesh network and core services exist before agents start.
Write-Host "🔧 Starting infrastructure..."
docker compose -f docker-compose.infra.yml up -d --wait --wait-timeout 240

# 3. Launch full mesh (infra + agents) with build.
# Keeping both files here is required because prod services depend_on infra service names.
Write-Host "🧠 Starting cognitive/voice agents..."
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d --build --remove-orphans

Write-Host "✅ System Starting..."
Write-Host "📊 Checking container status..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
