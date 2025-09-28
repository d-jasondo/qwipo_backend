# Production-ready Dockerfile for Qwipo B2B API
FROM python:3.11-slim

# System deps (minimal). Heavy BLAS/LAPACK/Fortran build deps are not needed because
# NumPy/SciPy wheels bundle OpenBLAS on Linux. This avoids apt errors on slim images.
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates \
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
    PYTHONPATH=/app \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

# Expose port
EXPOSE 8000

# Start a lightweight single-process Uvicorn server (good for free tier)
CMD ["bash", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info"]
