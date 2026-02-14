# Start AI Friend in PRODUCTION Mode
# Usage: ./scripts/start_prod.ps1

Write-Host "🚀 Launching AI Friend (Production Mesh)..."

# 1. Ensure .env exists
if (-not (Test-Path ".env")) {
    Write-Error "❌ .env file missing! Please create one from .env.example"
    exit 1
}

# 2. Support for legacy .env loading in PowerShell if needed, 
# strictly rely on Docker Compose reading .env natively.

# 3. Launch Docker Compose Stack
# We merge infra (databases) and prod (agents)
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d --remove-orphans

Write-Host "✅ System Starting..."
Write-Host "📊 Checking container status..."
Start-Sleep -Seconds 5
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
