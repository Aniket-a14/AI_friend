# AI Friend Mesh Initialization Script (Windows)

Write-Host "🌊 Initializing AI Friend Sovereign Mesh Layer..." -ForegroundColor Cyan

# 1. Create Docker Network
Write-Host "Creating 'ai-mesh' bridge network..."
docker network create ai-mesh 2>$null

# 2. Check for .env files
if (!(Test-Path "backend\.env")) {
    Write-Host "Copying backend\.env.example to .env..."
    Copy-Item "backend\.env.example" "backend\.env"
}

if (!(Test-Path "frontend\.env")) {
    Write-Host "Copying frontend\.env.example to .env..."
    Copy-Item "frontend\.env.example" "frontend\.env"
}

Write-Host "`n✅ Initialization complete!" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "1. Open backend\.env and add your GEMINI_API_KEY."
Write-Host "2. Run 'docker-compose -f docker-compose.infra.yml up -d' to start the backbone."
Write-Host "3. Run 'docker-compose up -d --build' to start the agents."
