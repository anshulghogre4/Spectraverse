# NOTE: python:3.13-slim has residual CVEs in Python's bundled libs.
# Pin to a digest once a patched release is available upstream.
FROM python:3.13-slim

WORKDIR /app

# Patch OS-level CVEs + install system deps
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    gcc \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer-cache friendly)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/app ./app
COPY semantic_mappings.json .

EXPOSE 8000

# Use Python for health check (curl not available in slim image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
