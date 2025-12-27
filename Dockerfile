# ===========================================
# VN-QUANT Trading System - Production Image
# ===========================================
# Multi-stage build for optimized image size

# Stage 1: Builder
FROM python:3.10-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements_quant.txt requirements_production.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels \
    -r requirements.txt \
    -r requirements_quant.txt \
    -r requirements_production.txt

# Stage 2: Runtime
FROM python:3.10-slim

LABEL maintainer="VN-QUANT Team"
LABEL version="4.0"
LABEL description="VN-QUANT Agentic Trading System"

# Create non-root user
RUN groupadd -r vnquant && useradd -r -g vnquant vnquant

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /build/wheels /wheels

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Copy application code
COPY --chown=vnquant:vnquant . .

# Create necessary directories
RUN mkdir -p logs data data/historical data/trading && \
    chown -R vnquant:vnquant logs data

# Switch to non-root user
USER vnquant

# Expose ports
EXPOSE 8003
EXPOSE 9090
EXPOSE 8501

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    API_HOST=0.0.0.0 \
    API_PORT=8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8003/ || exit 1

# Default command (can be overridden)
CMD ["python", "vn_quant_api.py"]
