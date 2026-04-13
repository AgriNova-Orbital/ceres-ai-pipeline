FROM python:3.12-bookworm AS base

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    APP_DB_PATH=/app/state/app.db \
    REDIS_URL=redis://redis:6379/0 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
    proj-bin \
    libhdf5-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

FROM base AS deps-runtime
RUN uv sync --frozen --no-install-project --extra ml --extra distributed

FROM base AS deps-dev
RUN uv sync --frozen --no-install-project --dev --extra ml --extra distributed

FROM deps-dev AS dev
COPY . .
RUN mkdir -p /app/state /app/data /app/runs /app/reports /app/logs
ENV FLASK_ENV=development \
    RQ_LOG_LEVEL=DEBUG
EXPOSE 5055
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:5055", "--workers", "1", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "debug", "apps.wheat_risk_webui:create_app()"]

FROM deps-runtime AS beta
COPY . .
RUN mkdir -p /app/state /app/data /app/runs /app/reports /app/logs
ENV FLASK_ENV=production \
    RQ_LOG_LEVEL=INFO
EXPOSE 5055
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:5055", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "apps.wheat_risk_webui:create_app()"]

FROM deps-runtime AS release
COPY . .
RUN mkdir -p /app/state /app/data /app/runs /app/reports /app/logs
ENV FLASK_ENV=production \
    RQ_LOG_LEVEL=WARNING
EXPOSE 5055
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:5055", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "warning", "apps.wheat_risk_webui:create_app()"]
