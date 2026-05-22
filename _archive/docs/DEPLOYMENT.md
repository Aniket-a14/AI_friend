# 🚀 Deployment Guide (CVS-1.0: Perceptual Mastery)

Production deployment strategies for the AI Friend platform, optimized for the **Cognitive Voice System (CVS-1.0)**.

---

## Table of Contents

1. [Production Checklist](#production-checklist)
2. [CVS-1.0 Runtime Baseline](#cvs-10-runtime-baseline)
3. [Solid State Mesh Hardening](#solid-state-mesh-hardening)
4. [Deployment Strategies](#deployment-strategies)
5. [Cloud Platforms](#cloud-platforms)
6. [SSL/HTTPS Setup](#sslhttps-setup)
7. [Environment Configuration](#environment-configuration)
8. [Monitoring & Logging](#monitoring--logging)
9. [Scaling](#scaling)
10. [Troubleshooting](#troubleshooting)

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
- [ ] Review [SECURITY.md](../../SECURITY.md)

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
- [ ] Track CVS behavioral metrics: first-audio latency, speculative pause duration, resume latency, memory surfacing frequency, and persona validation failures.

---

## 🛠️ CVS-1.0 Runtime Baseline (April 2026)

CVS-1.0 requires a state-aware runtime to maintain sub-280ms perceived latency.

### 1. Essential Configuration

Ensure your `backend/.env` contains the Perceptual Mastery flags:

```bash
# CVS-1.0 Runtime Config
VOICE_RUNTIME_MODE=perceptual
SEGMENTATION_FEEDBACK_ENABLED=True
JITTER_BUFFER_MAX_MS=25
PCM_SAMPLE_RATE=32000
```

### 2. Hardware Profiles

#### 🏎️ Extreme Profile (RTX 4090 / M4 Max)

- **Cognitive Path**: `llama3.2:3b` (4-bit quant)

- **Signal Path**: V4 Weights with `media_type: raw`
- **Latency Target**: <180ms
- **Optimization**: Disable all post-synthesis filters; use direct PCM injection.

#### 🍎 Elite Profile (M4 Pro / M4 Max)

- **Cognitive Path**: `llama3.2:3b` (Metal-Optimized)

- **Signal Path**: V4 Weights with `device="mps"`
- **Unified Memory**: Ensure at least 8GB of the 24GB+ pool is free for STT/TTS residency.
- **Latency Target**: <210ms
- **Optimization**: Use the **MPS (Metal Performance Shaders)** backend for PyTorch to eliminate CPU bottlenecks.

#### ⚖️ Balanced Profile (RTX 3070 / M2)

- **Cognitive Path**: `llama3.2:1b` (8-bit quant)

- **Signal Path**: V4 Weights
- **Latency Target**: <250ms
- **Optimization**: Enable `soxr` resampling for UI-specific playback if needed.

---

## 🛡️ Solid State Mesh Hardening (April 2026)

The CVS-1.0 Mesh has been hardened for **Zero-Drift Portability**. This ensures the AI Friend can be deployed on any machine while maintaining identity continuity and security.

### 1. Decentralized Credential Enforcer

Hardcoded credentials are strictly rejected. The mesh utilizes the **Solid State Enforcer** in `backend/app/knowledge/graph_db.py` to prevent insecure booting.

- **NEO4J_AUTH**: Must be provided via `.env`. Default `neo4j/password` will trigger a security violation.
- **Environment Isolation**: All services use internal mesh aliases (`nats_mesh`, `postgres_db`) rather than `localhost` to allow cross-machine Docker networking.

### 2. Relational Hydration (Prisma 7.7.0)

The database schema is managed via the modern Prisma 7.7.0 standard. On any new PC, you MUST synchronize the persistent state:

```bash
# Set your local DB secret in the terminal session
$env:DIRECT_URL="postgresql://ai_friend:[PASSWORD]@localhost:5432/ai_friend_db"
cd frontend
npx prisma db push
```

### 3. Mesh Portability Checklist

Before moving the project to a new machine:

- [ ] **Sanity Check .env**: Ensure all variables in `.env.example` are populated.
- [ ] **Relative Paths**: Verify `docker-compose.infra.yml` uses relative mounts (e.g., `./backend`).
- [ ] **Clean Volume Recovery**: To reset a machine's data completely, use `docker compose down -v`.
- [ ] **AI Perception**: Ensure `requirements-ai.txt` is installed to support `sherpa-onnx` (SenseVoice).
- [ ] **Agent Context Ledger**: Read `.agents/CONTEXT.md` before modifying runtime behavior and update it after deployment-impacting changes.
- [ ] **Test Runner**: Prefer `backend/.venv/Scripts/python.exe -m pytest` on Windows because the global Anaconda environment may not load the same packages.

### 4. CVS Runtime Regression Suite

Before shipping changes to cognition, memory, STT, TTS, or mesh subjects, run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

The suite includes regression coverage for:

- State hydration avoiding stale graph cache.
- Speculative stop rejection and final stop confirmation.
- Shared live identity ownership between cognition and reflection.
- BrainAgent startup connection ordering.
- Emotion markup sanitization.
- Memory surfacing novelty suppression.

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

### Strategy 2: Production Hardening (Docker Compose)

**Best for**: Self-hosted servers, workstations, total control.

#### 1. Tiered Image Architecture

CVS-1.0 relies on tiered Docker images to isolate the cognitive load from the signal runtime.

```bash
# Build the Cognitive Base (LLM & Logic)
docker build -t cvs/brain:1.0 -f backend/Dockerfile.base backend/

# Build the Signal Layer (TTS & Audio Rendering)
docker build -t cvs/voice:1.0 -f backend/Dockerfile.full backend/
```

#### 2. Launch the Mesh

Infrastructure must be healthy before agents initialize their jitter buffers.

**Unified launch (infra + agent mesh)**

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d --build
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

CVS-1.0 includes specialized health metrics beyond standard Uptime.

**Perceptual Health Checks**:

1. **Pulse Check**: `nats sub "voice.segmentation_feedback"`
2. **Jitter Check**: Check `VoiceAgent` logs for `Buffer Recovery` events.
3. **Sync Check**: Ensure the system resyncs every 5 minutes (automatic).

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
**Solution**: Ensure SSL is configured (WSS required) and `proxy_read_timeout` is set to `86400`.

### High Memory Usage

**Symptom**: Backend container using excessive memory
**Solution**: Limit memory entries (`MAX_MEMORY_ITEMS=100`) and set Docker memory limits.

### Pulse Loop Latency

**Symptom**: Voice response feels staggered or robotic.
**Solution**: Check for clock drift in logs (`NATS Sync`). Ensure Signaling and VoiceAgent are in the same cloud region.
