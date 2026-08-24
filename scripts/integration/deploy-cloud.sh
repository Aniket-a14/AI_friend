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

  # P2-12: .env.example ships ENVIRONMENT=production as of this fix, so
  # config.py's placeholder-secret guard now refuses to boot with the
  # example's literal "your_..._here" values still in place -- which is the
  # guard doing exactly its job. Before this, that guard could never fire
  # here at all (ENVIRONMENT was "development" by default), so this script
  # was shipping a publicly-reachable cloud instance with well-known
  # placeholder Postgres/Neo4j/LiveKit credentials. Generate real random
  # ones instead of working around the guard.
  echo "🔐 Generating random secrets for this cloud deployment..."
  PG_PASS=$(openssl rand -hex 24)
  NEO4J_PASS=$(openssl rand -hex 24)
  LK_KEY=$(openssl rand -hex 16)
  LK_SECRET=$(openssl rand -hex 32)
  sed -i "s#POSTGRES_PASSWORD=your_password_here#POSTGRES_PASSWORD=${PG_PASS}#" .env
  sed -i "s#NEO4J_PASSWORD=your_graph_password_here#NEO4J_PASSWORD=${NEO4J_PASS}#" .env
  sed -i "s#NEO4J_AUTH=neo4j/your_graph_password_here#NEO4J_AUTH=neo4j/${NEO4J_PASS}#" .env
  sed -i "s#LIVEKIT_API_KEY=your_api_key_here#LIVEKIT_API_KEY=${LK_KEY}#" .env
  sed -i "s#LIVEKIT_API_SECRET=your_api_secret_here#LIVEKIT_API_SECRET=${LK_SECRET}#" .env
  sed -i "s#LIVEKIT_KEYS=\"your_api_key: your_api_secret\"#LIVEKIT_KEYS=\"${LK_KEY}: ${LK_SECRET}\"#" .env
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
docker exec brain_agent python scripts/bootstrap/setup_nats_streams.py

# 6. Finalize Deployment
echo "🧠 Launching Cognitive Agents..."
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d

echo "✅ --- DEPLOYMENT COMPLETE ---"
echo "Mesh is now active on this Cloud Instance."
echo "Use 'docker ps' to verify all 22 containers."
echo "Run 'python3 scripts/research/hard_benchmark.py' to generate paper results."
