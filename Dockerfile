# Production-ready Dockerfile for Qwipo B2B API
FROM python:3.11-slim

# System deps
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    gfortran \
    libatlas-base-dev \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (better layer cache)
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Environment
ENV PORT=8000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Start with Gunicorn + Uvicorn worker (bind to PORT env var)
CMD ["bash", "-lc", "gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 120"]
