# 🚀 Deployment Guide

Production deployment strategies for AI Friend platform.

---

## Table of Contents

1. [Production Checklist](#production-checklist)
2. [Deployment Strategies](#deployment-strategies)
3. [Cloud Platforms](#cloud-platforms)
4. [SSL/HTTPS Setup](#sslhttps-setup)
5. [Environment Configuration](#environment-configuration)
6. [Monitoring & Logging](#monitoring--logging)
7. [Scaling](#scaling)
8. [Troubleshooting](#troubleshooting)

---

## Production Checklist

Before deploying to production, ensure you have completed the following:

### Security
- [ ] Set `DEBUG=False` in backend/.env
- [ ] Configure HTTPS/WSS endpoints (SSL is **required** for microphone access)
- [ ] Set up proper CORS origins (no wildcards in production)
- [ ] Rotate API keys and use environment variables
- [ ] Enable rate limiting
- [ ] Configure database backups
- [ ] Review [SECURITY.md](./SECURITY.md)

### Performance
- [ ] Test with production-scale traffic
- [ ] Configure resource limits (CPU, memory)
- [ ] Enable caching where appropriate
- [ ] Optimize database queries
- [ ] Set up CDN for static assets

### Monitoring
- [ ] Configure logging aggregation
- [ ] Set up error tracking (e.g., Sentry)
- [ ] Enable health check endpoints
- [ ] Configure alerting for critical failures
- [ ] Set up uptime monitoring

---

## Deployment Strategies

### Strategy 1: Split Deployment (Recommended)

**Best for**: Production environments, auto-scaling, ease of management

Deploy frontend and backend separately for optimal performance and scalability.

#### Frontend → Vercel

Vercel is optimized for Next.js applications.

```bash
# 1. Connect GitHub repository to Vercel
# 2. Configure project settings:
#    - Framework Preset: Next.js
#    - Root Directory: frontend
#    - Build Command: npm run build
#    - Output Directory: .next

# 3. Set environment variables:
NEXT_PUBLIC_BACKEND_URL=https://api.yourdomain.com
```

**Vercel Configuration** (`vercel.json`):
```json
{
  "buildCommand": "cd frontend && npm run build",
  "devCommand": "cd frontend && npm run dev",
  "installCommand": "cd frontend && npm install",
  "framework": "nextjs",
  "outputDirectory": "frontend/.next"
}
```

#### Backend → Railway / Render / Fly.io

These platforms support long-running WebSocket connections.

**Railway**:
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and initialize
railway login
railway init

# 3. Deploy
railway up

# 4. Set environment variables via Railway dashboard
```

**Dockerfile** (already included in `backend/Dockerfile`):
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### Strategy 2: Combined Deployment (Docker Compose)

**Best for**: Self-hosted servers, VPS, total control

Deploy both frontend and backend together using Docker Compose.

#### Prerequisites

- VPS (DigitalOcean, AWS EC2, Linode, Hetzner)
- Docker & Docker Compose installed
- Domain name with DNS configured

#### Setup Steps

```bash
# 1. Clone repository on server
git clone https://github.com/yourusername/AI_friend.git
cd AI_friend

### Quick Start for New Users

If you are setting up the project for the first time, use the provided automation scripts to handle network and environment configuration.

#### Windows (PowerShell)
```powershell
.\setup_mesh.ps1
```

#### Linux / macOS (Bash)
```bash
chmod +x setup_mesh.sh
./setup_mesh.sh
```

---

# 2. Configure environment
Edit the generated `.env` files with your actual credentials:
- `backend/.env`: Add `GEMINI_API_KEY`.
- `frontend/.env`: (Optional) Change `NEXT_PUBLIC_BACKEND_URL` if not on localhost.

# 3. Build and start services (Dual-File)
# Launch Infrastructure first
docker-compose -f docker-compose.infra.yml up -d

# Launch Agent Mesh
docker-compose up -d --build

# 4. Verify services are running
docker ps
docker logs ai_friend-backend-1
docker logs ai_friend-frontend-1
```

#### Production Docker Compose

**`docker-compose.prod.yml`**:
```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      target: runtime
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    environment:
      - DEBUG=False
      - ALLOWED_ORIGINS=https://yourdomain.com
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/status"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      target: runner
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_BACKEND_URL=https://api.yourdomain.com
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    restart: unless-stopped
    depends_on:
      - backend
```

---

## Cloud Platforms

### AWS (ECS/Fargate)

**Architecture**:
```
ALB → ECS Service (Frontend) → Target Group
ALB → ECS Service (Backend) → Target Group
```

**Steps**:
1. Create ECR repositories for frontend and backend
2. Push Docker images to ECR
3. Create ECS task definitions
4. Configure Application Load Balancer
5. Set up Auto Scaling

**Example Task Definition** (`backend-task.json`):
```json
{
  "family": "ai-friend-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "your-ecr-repo/backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DEBUG",
          "value": "False"
        }
      ],
      "secrets": [
        {
          "name": "GEMINI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:gemini-key"
        }
      ]
    }
  ]
}
```

---

### Google Cloud (Cloud Run)

**Steps**:
```bash
# 1. Build and push images
gcloud builds submit --tag gcr.io/PROJECT_ID/backend ./backend
gcloud builds submit --tag gcr.io/PROJECT_ID/frontend ./frontend

# 2. Deploy services
gcloud run deploy backend \
  --image gcr.io/PROJECT_ID/backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DEBUG=False

gcloud run deploy frontend \
  --image gcr.io/PROJECT_ID/frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

### Azure (Container Instances)

**Steps**:
```bash
# 1. Create resource group
az group create --name ai-friend-rg --location eastus

# 2. Create container registry
az acr create --resource-group ai-friend-rg \
  --name aifriendregistry --sku Basic

# 3. Build and push images
az acr build --registry aifriendregistry \
  --image backend:latest ./backend

# 4. Deploy container instances
az container create \
  --resource-group ai-friend-rg \
  --name backend \
  --image aifriendregistry.azurecr.io/backend:latest \
  --cpu 1 --memory 2 \
  --ports 8000 \
  --environment-variables DEBUG=False
```

---

## SSL/HTTPS Setup

### Option 1: Nginx Reverse Proxy + Let's Encrypt

**Install Nginx and Certbot**:
```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

**Nginx Configuration** (`/etc/nginx/sites-available/ai-friend`):
```nginx
# Frontend
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

# Backend API + WebSocket
server {
    listen 80;
    server_name api.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # WebSocket specific
        proxy_read_timeout 86400;
    }
}
```

**Enable SSL**:
```bash
sudo certbot --nginx -d yourdomain.com -d api.yourdomain.com
sudo systemctl reload nginx
```

---

### Option 2: Caddy (Automatic HTTPS)

**Caddyfile**:
```caddy
yourdomain.com {
    reverse_proxy localhost:3000
}

api.yourdomain.com {
    reverse_proxy localhost:8000
}
```

**Start Caddy**:
```bash
sudo caddy run --config /etc/caddy/Caddyfile
```

---

## Environment Configuration

### Production Environment Variables

**Backend** (`backend/.env`):
```bash
# Core
DEBUG=False
AI_NAME=AI Friend
LOCATION_CONTEXT=Global

# Security
ALLOWED_ORIGINS=https://yourdomain.com
SECRET_KEY=your-secret-key-here

# APIs
GEMINI_API_KEY=your-production-key
SUPABASE_URL=your-production-url
SUPABASE_KEY=your-production-key

# Performance
MAX_MEMORY_ITEMS=1000
VISION_FPS=1
```

**Frontend** (`frontend/.env`):
```bash
NEXT_PUBLIC_BACKEND_URL=https://api.yourdomain.com
```

---

## Monitoring & Logging

### Logging Setup

**Backend Logging** (`backend/app/logging_config.py`):
```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # File handler
    handler = RotatingFileHandler(
        'app.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
```

### Health Checks

**Endpoint**: `GET /status`

**Docker Health Check**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/status"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## Scaling

### Horizontal Scaling

**Load Balancer Configuration**:
```nginx
upstream backend {
    least_conn;
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}

server {
    location / {
        proxy_pass http://backend;
    }
}
```

### Database Connection Pooling

**Backend** (`backend/app/database.py`):
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

---

## Troubleshooting

### WebSocket Connection Issues

**Symptom**: WebSocket fails to connect in production

**Solutions**:
1. Ensure SSL is configured (WSS required)
2. Check proxy timeout settings
3. Verify CORS configuration
4. Check firewall rules

**Nginx WebSocket Config**:
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 86400;
```

### High Memory Usage

**Symptom**: Backend container using excessive memory

**Solutions**:
1. Limit memory entries: `MAX_MEMORY_ITEMS=100`
2. Enable garbage collection
3. Set Docker memory limits
4. Monitor with `docker stats`

### SSL Certificate Issues

**Symptom**: "NET::ERR_CERT_AUTHORITY_INVALID"

**Solutions**:
```bash
# Renew Let's Encrypt certificate
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run

# Check certificate expiry
sudo certbot certificates
```

---

**For architecture details, see [ARCHITECTURE.md](./ARCHITECTURE.md)**  
**For security best practices, see [SECURITY.md](./SECURITY.md)**
