# Backend Dockerfile - Tiered Multi-Stage Optimization
# 1. BASE: OS-level dependencies
FROM python:3.12-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-openbsd \
    libportaudio2 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 1.5. RUST WHEEL BUILDER: Builds the Python extension wheel
FROM rust:1-bookworm AS rust-wheel-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages maturin
COPY Cargo.toml Cargo.lock pyproject.toml ./
COPY crates ./crates
# maturin reads [tool.maturin] from whichever pyproject.toml sits in the
# invoking cwd, regardless of --manifest-path (see pyproject.toml's own
# comment on this). Without it copied in here, this build silently drops the
# "extension-module" feature request and produces a libpython-linked wheel
# that can fail to import in the runtime image -- the exact defect this
# feature config exists to avoid.
RUN maturin build --release --manifest-path crates/cognitive-rust/Cargo.toml --out target/wheels

# 2. SLIM BUILDER: Core dependencies only
FROM base AS slim-builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements-base.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements-base.txt

# Copy and install the cognitive-rust wheel built in the Rust stage
COPY --from=rust-wheel-builder /build/target/wheels/ /tmp/wheels/
RUN pip install /tmp/wheels/*.whl

# 3. FULL BUILDER: Includes heavy AI/Vision dependencies
FROM slim-builder AS full-builder
COPY requirements-ai.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-ai.txt

# 4. SLIM RUNTIME: For signaling & non-heavy agents
FROM base AS slim
COPY --from=slim-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Create a non-root user
RUN groupadd -g 1001 appgroup && useradd -m -u 1001 -g appgroup appuser \
    && chown -R appuser:appgroup /app \
    && install -d -o appuser -g appgroup /app/data
USER appuser
COPY --chown=appuser:appgroup . .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/status || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# 5. FULL RUNTIME: For STT and Vision agents
FROM base AS full
COPY --from=full-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN groupadd -g 1001 appgroup && useradd -m -u 1001 -g appgroup appuser \
    && chown -R appuser:appgroup /app \
    && install -d -o appuser -g appgroup /app/data
USER appuser
COPY --chown=appuser:appgroup . .
CMD ["python", "main.py"]
