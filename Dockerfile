FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
WORKDIR /app
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends libsndfile1 ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 shield && useradd -r -u 10001 -g shield shield
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY deploy ./deploy
COPY compose*.yaml ./
COPY model-assets.sha256 ./
RUN mkdir -p /data/uploads && chown -R shield:shield /data
ARG SOURCE_REVISION=development
LABEL org.opencontainers.image.revision=$SOURCE_REVISION
USER 10001:10001
ENV UPLOAD_FOLDER=/data/uploads MODEL_ROOT=/models
STOPSIGNAL SIGTERM
CMD ["gunicorn", "--config", "gunicorn.conf.py", "server:app"]
