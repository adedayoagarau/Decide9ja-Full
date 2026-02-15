# Decide9ja Backend - Production Dockerfile for Railway
# Multi-stage build for smaller image size

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    tesseract-ocr \
    tesseract-ocr-eng \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /home/decide9ja/.local
ENV PATH=/home/decide9ja/.local/bin:$PATH

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 decide9ja

# Copy Python packages directly with correct ownership (avoids expensive chown -R)
COPY --from=builder --chown=decide9ja:decide9ja /root/.local /home/decide9ja/.local
ENV PATH=/home/decide9ja/.local/bin:$PATH

# Copy application code with correct ownership
COPY --chown=decide9ja:decide9ja . .

USER decide9ja

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    PORT=8000

# Expose port
EXPOSE ${PORT}

# Run with gunicorn for production (uvicorn workers)
CMD ["sh", "-c", "gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT} --timeout 120"]
