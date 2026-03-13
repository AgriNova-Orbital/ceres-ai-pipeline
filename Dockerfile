FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1 \
    APP_DB_PATH=/app/state/app.db \
    REDIS_URL=redis://redis:6379/0

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --dev --extra ml --extra distributed

COPY . .

RUN mkdir -p /app/state /app/data /app/runs /app/reports /app/logs

EXPOSE 5055

CMD ["uv", "run", "scripts/main.py"]
