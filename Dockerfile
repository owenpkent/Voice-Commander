# Voice Commander Cloud - Dockerfile (CPU)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps (add build tools for webrtcvad)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates gcc g++ python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY cloud/requirements.txt /app/cloud/requirements.txt
RUN pip install --no-cache-dir -r /app/cloud/requirements.txt

# Copy app
COPY . /app

# Default environment (override at runtime)
ENV VC_S3_BUCKET=voice-commander-data-opk \
    VC_STREAM_MODEL=tiny.en \
    VC_STREAM_DEVICE=cpu \
    VC_STREAM_COMPUTE=int8 \
    VC_STREAM_MIN_SEC=0.8 \
    VC_BATCH_MODEL=small \
    VC_BATCH_DEVICE=cpu \
    VC_BATCH_COMPUTE=int8

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "cloud.main:app", "--host", "0.0.0.0", "--port", "8000"]
