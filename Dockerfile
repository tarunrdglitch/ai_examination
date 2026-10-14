# DL Procted Examination - application image (works on x86_64 and the aarch64 DGX Spark)
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake pkg-config libopenblas-dev liblapack-dev \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
        xvfb xauth x11-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip wheel setuptools \
    && pip install -r requirements.txt \
    && pip install gunicorn==21.2.0

COPY . .
RUN mkdir -p database recordings violation_screenshots && chmod +x docker-entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["./docker-entrypoint.sh"]
