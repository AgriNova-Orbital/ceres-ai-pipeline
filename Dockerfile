FROM python:3.12-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1 \
    APP_DB_PATH=/app/state/app.db \
    REDIS_URL=redis://redis:6379/0 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies for numpy, rasterio, matplotlib, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
    proj-bin \
    libhdf5-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency definitions first to leverage Docker cache
COPY pyproject.toml uv.lock ./
RUN uv sync --dev --extra ml --extra distributed

# Copy application code
COPY . .

RUN mkdir -p /app/state /app/data /app/runs /app/reports /app/logs

EXPOSE 5055

CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:5055", "--workers", "2", "apps.wheat_risk_webui:create_app()"]
