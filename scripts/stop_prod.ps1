# Stop AI Friend Production Stack
# Usage: ./scripts/stop_prod.ps1

Write-Host "🛑 Stopping AI Friend Production Stack..."

docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml down

Write-Host "✅ System Stopped."
