#!/bin/bash
set -e

# 1. Ensure Redis is running
if command -v redis-server &> /dev/null; then
    echo "Redis is already installed. Checking status..."
    # This assumes systemd or background process
else
    echo "No local Redis found. Attempting to start via Docker..."
    if command -v docker &> /dev/null; then
        # Check if container exists
        if [ ! "$(docker ps -q -f name=my-redis)" ]; then
            if [ "$(docker ps -aq -f status=exited -f name=my-redis)" ]; then
                # Cleanup if exited
                docker rm my-redis
            fi
            echo "Starting Redis container..."
            docker run -d --name my-redis -p 6379:6379 redis:7-alpine
        else
            echo "Redis container is already running."
        fi
    else
        echo "Warning: Neither local Redis nor Docker found."
        echo "Setting USE_FAKEREDIS=1 (Warning: Jobs will not run in background worker)"
        export USE_FAKEREDIS=1
    fi
fi

# 2. Export Redis URL for application
export REDIS_URL=redis://localhost:6379/0

# 3. Start Services
echo "Starting WebUI (Gunicorn, 1 worker) and RQ Worker..."

# Start RQ Worker in background
uv run python -m modules.jobs.worker > rq_worker.log 2>&1 &
WORKER_PID=$!

# Start WebUI in foreground
uv run gunicorn --bind 0.0.0.0:5055 --workers 1 "apps.wheat_risk_webui:create_app()"

# Cleanup on exit
kill $WORKER_PID
if command -v docker &> /dev/null && [ "$(docker ps -q -f name=my-redis)" ]; then
    docker stop my-redis
    docker rm my-redis
fi
