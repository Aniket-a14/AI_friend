# Backend Dockerfile - Optimized for Production
# STAGE 1: Builder
FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    portaudio19-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies in a virtual environment for isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# STAGE 2: Runtime
FROM python:3.10-slim AS runtime

WORKDIR /app

# Install runtime dependencies (minimal)
RUN apt-get update && apt-get install -y \
    libportaudio2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create a non-root user
RUN groupadd -g 1001 appgroup && \
    useradd -m -u 1001 -g appgroup appuser
USER appuser

# Copy application code with correct ownership
COPY --chown=appuser:appgroup . .

# Metadata and labels
LABEL org.opencontainers.image.source="https://github.com/Aniket-a14/Ai_friend"
LABEL org.opencontainers.image.description="Pankudi AI Backend - Human-like Voice AI"
LABEL org.opencontainers.image.version="2.1.1"

EXPOSE 8000

# Healthcheck to monitor app status
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/status || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
