FROM python:3.11-slim

# Metadata
LABEL description="SQL Query Debugging Environment — OpenEnv"
LABEL openenv="true"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Set PYTHONPATH to include the root directory for module discovery
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies first (cached layer)
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy and install Python dependencies (separate layer for cache efficiency)
COPY requirements.txt .
COPY pyproject.toml .
COPY uv.lock .

# Use pip cache and install dependencies efficiently
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install -e . && \
    rm -rf /root/.cache/pip

# Copy application code (exclude unnecessary files)
COPY --chown=appuser:appuser . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/logs /app/benchmark_output && \
    chown -R appuser:appuser /app/logs /app/benchmark_output

USER appuser

# Health check — validators will call this
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Expose port (HF Spaces uses 7860)
EXPOSE 7860

# Optimize Python runtime
ENV PYTHONOPTIMIZE=1

# Start the API server using module syntax to ensure proper path discovery
CMD ["python", "-m", "server.app"]