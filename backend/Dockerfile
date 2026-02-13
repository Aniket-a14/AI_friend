# Backend Dockerfile - Tiered Multi-Stage Optimization
# 1. BASE: OS-level dependencies
FROM python:3.10-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    curl \
    libportaudio2 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. SLIM BUILDER: Core dependencies only
FROM base AS slim-builder
RUN apt-get update && apt-get install -y build-essential portaudio19-dev
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements-base.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-base.txt

# 3. FULL BUILDER: Includes heavy AI/Vision dependencies
FROM slim-builder AS full-builder
COPY requirements-ai.txt .
RUN pip install --no-cache-dir -r requirements-ai.txt

# 4. SLIM RUNTIME: For signaling & non-heavy agents
FROM base AS slim
COPY --from=slim-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Create a non-root user
RUN groupadd -g 1001 appgroup && useradd -m -u 1001 -g appgroup appuser
USER appuser
COPY --chown=appuser:appgroup . .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/status || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# 5. FULL RUNTIME: For STT and Vision agents
FROM base AS full
COPY --from=full-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN groupadd -g 1001 appgroup && useradd -m -u 1001 -g appgroup appuser
USER appuser
COPY --chown=appuser:appgroup . .
CMD ["python", "main.py"]
