# ============================================================
# WORKER SERVICE - Multi-stage Build (includes ML models)
# ============================================================
FROM python:3.11-slim AS base

# System dependencies for document parsing + ML models
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libreoffice-headless \
    poppler-utils \
    tesseract-ocr \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install Python dependencies (core + ML)
COPY requirements.txt requirements-ml.txt .
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt

# Pre-download ML models at build time (cached in layer)
ARG HF_TOKEN
RUN python -c "
from faster_whisper import WhisperModel
WhisperModel('base', device='cpu', download_root='/models')
from pyannote.audio import Pipeline
Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token='${HF_TOKEN}', cache_dir='/models')
" || echo "Model download failed (HF_TOKEN may not be set at build time)"

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/

# Change ownership
RUN chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "app.workers.main"]