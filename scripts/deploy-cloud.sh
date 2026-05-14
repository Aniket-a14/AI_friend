#!/bin/bash
# AI Friend - Cloud GPU Deployment Engine (CVS-1.0)
# Automatically initializes the Sovereign Mesh on a remote GPU instance.

set -e

echo "🚀 --- Initializing Cloud Sovereign Mesh ---"

# 1. Environment Check
if ! [ -x "$(command -v docker)" ]; then
  echo "❌ Error: Docker is not installed. Please install Docker first." >&2
  exit 1
fi

# 2. Setup Environment Variables
if [ ! -f .env ]; then
  echo "📝 Creating default .env for Cloud Deployment..."
  cp .env.example .env
  # Update NATS to listen on all interfaces for the cloud bridge
  sed -i 's/127.0.0.1/0.0.0.0/g' .env
fi

# 3. Pull & Build Mesh
echo "🏗️ Building Sovereign Mesh Containers..."
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml build

# 4. Bootstrap Infrastructure
echo "📡 Starting Infrastructure (NATS, Databases)..."
docker compose -f docker-compose.infra.yml up -d

# 5. Wait for NATS and Hydrate Streams
echo "⏳ Waiting for NATS Mesh stabilization..."
sleep 10

# Ensure we have python dependencies for hydration
pip install nats-py pydantic-settings > /dev/null 2>&1 || echo "⚠️ Non-critical: Local pip install failed, skipping host-side hydration."

echo "💧 Hydrating NATS Mesh Contracts..."
docker exec brain_agent python scripts/setup_nats_streams.py

# 6. Finalize Deployment
echo "🧠 Launching Cognitive Agents..."
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d

echo "✅ --- DEPLOYMENT COMPLETE ---"
echo "Mesh is now active on this Cloud Instance."
echo "Use 'docker ps' to verify all 22 containers."
echo "Run 'python3 scripts/research/hard_benchmark.py' to generate paper results."
