# BAET - Binance Adaptive Ensemble Trader
# Multi-stage build for smaller image

FROM python:3.13-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml requirements.txt uv.lock ./

# Install Python dependencies
RUN uv sync --all-extras --no-cache

# Copy source code
COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/
COPY .env.example .env.example
COPY README.md ./

# Create data directories
RUN mkdir -p data/raw data/processed data/results logs artifacts

# Set environment variables
ENV PYTHONPATH=/app/src
ENV BAET_MODE=paper

# Default command
CMD ["uv", "run", "python", "-m", "baet"]
