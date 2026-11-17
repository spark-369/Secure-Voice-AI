# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# SecureVoice AI — backend image (API + Celery worker share this image)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl is needed for the container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Torch is pulled from the CPU wheel index to keep the image lean.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/tests ./tests

# Non-root runtime user + writable data directories.
RUN useradd --create-home appuser \
    && mkdir -p /data/chroma /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /data /home/appuser /app

USER appuser

ENV HF_HOME=/home/appuser/.cache/huggingface \
    CHROMA_TELEMETRY=false

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

# One worker: the LLM is loaded in-process, so scale replicas instead of workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
