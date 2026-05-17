# AI Friend - Host Vision Agent Launcher
# This script runs the vision agent on the host to enable screen capture on Windows.

# Get the project root directory (one level up from scripts folder)
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

$env:PYTHONPATH="backend"
$env:NATS_URL="nats://127.0.0.1:4222"
$env:OLLAMA_URL="http://127.0.0.1:11434"
$env:VLM_MODEL="moondream:latest"

Write-Host "📸 Starting AI Friend Host Vision Agent..." -ForegroundColor Cyan
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host "Connecting to NATS at $env:NATS_URL" -ForegroundColor Gray

python -m app.vision.agent
