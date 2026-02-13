#!/bin/bash

# AI Friend Mesh Initialization Script (Linux/macOS)

echo -e "\033[0;36m🌊 Initializing AI Friend Sovereign Mesh Layer...\033[0m"

# 1. Create Docker Network
echo "Creating 'ai-mesh' bridge network..."
docker network create ai-mesh 2>/dev/null

# 2. Check for .env files
if [ ! -f "backend/.env" ]; then
    echo "Copying backend/.env.example to .env..."
    cp backend/.env.example backend/.env
fi

if [ ! -f "frontend/.env" ]; then
    echo "Copying frontend/.env.example to .env..."
    cp frontend/.env.example frontend/.env
fi

echo -e "\n\033[0;32m✅ Initialization complete!\033[0m"
echo "Next steps:"
echo "1. Open backend/.env and add your GEMINI_API_KEY."
echo "2. Run 'docker-compose -f docker-compose.infra.yml up -d' to start the backbone."
echo "3. Run 'docker-compose up -d --build' to start the agents."
