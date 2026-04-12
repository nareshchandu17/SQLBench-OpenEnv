FROM python:3.11-slim

# Metadata
LABEL description="SQL Query Debugging Environment — OpenEnv"
LABEL openenv="true"

# Set working directory
WORKDIR /app

# Install system dependencies first (cached layer)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies (separate layer for cache efficiency)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check — validators will call this
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Expose port (HF Spaces uses 7860)
EXPOSE 7860

# Start the API server
CMD ["python", "server.py"]