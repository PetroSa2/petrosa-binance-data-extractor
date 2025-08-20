# Multi-stage Dockerfile for Petrosa TA Bot
# Optimized for production deployment with security and performance

# Build stage
FROM python:3.11-slim AS builder

# Build arguments
ARG VERSION=dev
ARG COMMIT_SHA=unknown
ARG BUILD_DATE=unknown

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim AS production

# Build arguments
ARG VERSION=dev
ARG COMMIT_SHA=unknown
ARG BUILD_DATE=unknown

# Metadata labels
LABEL org.opencontainers.image.title="Petrosa TA Bot" \
      org.opencontainers.image.description="Technical Analysis bot for cryptocurrency trading" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/petrosa/petrosa-bot-ta-analysis" \
      org.opencontainers.image.vendor="Petrosa" \
      org.opencontainers.image.licenses="MIT"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_VERSION="${VERSION}" \
    COMMIT_SHA="${COMMIT_SHA}" \
    BUILD_DATE="${BUILD_DATE}"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create application directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories
RUN mkdir -p logs tmp && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set Python path
ENV PYTHONPATH="/app:$PYTHONPATH"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Expose health check port
EXPOSE 8080

# Default command (can be overridden)
CMD ["python", "-m", "ta_bot.main"]

# Development stage (for local development)
FROM production AS development

# Switch back to root for development tools
USER root

# Install development dependencies
RUN pip install pytest pytest-cov flake8 mypy black isort ipython jupyter

# Install additional debugging tools
RUN apt-get update && apt-get install -y \
    vim \
    htop \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Switch back to appuser
USER appuser

# Expose port for Jupyter (if needed)
EXPOSE 8888

# Development command
CMD ["python", "-c", "print('Development container ready. Use docker exec to run commands.')"]

# Testing stage
FROM development AS testing

# Copy test files
COPY --chown=appuser:appuser tests/ tests/
COPY --chown=appuser:appuser requirements-dev.txt .

# Install test dependencies
USER root
RUN pip install -r requirements-dev.txt
USER appuser

# Run tests by default
CMD ["pytest", "tests/", "-v", "--cov=.", "--cov-report=html"]
