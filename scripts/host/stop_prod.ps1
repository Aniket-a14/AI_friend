# Stop AI Friend Production Stack
# Usage: ./scripts/stop_prod.ps1 [-PurgeVolumes]

param(
	[switch]$PurgeVolumes
)

Write-Host "🛑 Stopping AI Friend Production Stack..."

if ($PurgeVolumes) {
	Write-Host "🧹 Removing containers, networks, and named volumes..."
	docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml down -v --remove-orphans
} else {
	docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml down --remove-orphans
}

Write-Host "✅ System Stopped."
