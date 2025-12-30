# ============================================
# Video AI SaaS - Production Dockerfile
# Multi-stage build for optimized image size
# ============================================

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ffmpeg \
    libmagic1 \
    libpq-dev \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    libpq5 \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser -m -d /app appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p \
    /var/log/video-ai \
    /var/uploads \
    /var/temp \
    /var/logs \
    /var/processing \
    /var/outputs \
    && chown -R appuser:appuser /app /var/log/video-ai /var/uploads /var/temp /var/logs /var/processing /var/outputs

# Copy configuration files
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Switch to non-root user
USER appuser

# Environment variables
ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UPLOAD_FOLDER=/var/uploads \
    TEMP_FOLDER=/var/temp \
    LOG_FOLDER=/var/logs \
    PROCESSING_FOLDER=/var/processing \
    OUTPUTS_FOLDER=/var/outputs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose ports
EXPOSE 5000  # Flask app
EXPOSE 5555  # Flower (Celery monitoring)
EXPOSE 80    # Nginx

# Start command
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]