# Chontak API (FastAPI + Gunicorn/Uvicorn).
# Build context: repository root. Dockerfile location: /backend/Dockerfile

FROM python:3.14-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r /tmp/requirements.txt


FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=5001 \
    WEB_CONCURRENCY=4

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY backend/ /app/

RUN mkdir -p /app/logs && chown -R app:app /app
USER app

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

# Migrations run here, in the API container only.
# Bound on [::], which on Linux accepts IPv4 too. nginx resolves the service
# name to both families, and an IPv4-only listener cost every caller a refused
# connection and a retry. Binding both explicitly does not work: the second
# bind collides with the first and gunicorn refuses to start.
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind [::]:${PORT} --access-logfile - --error-logfile -"]
