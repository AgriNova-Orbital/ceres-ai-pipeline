#!/bin/bash
set -e

# ===========================================
# 1. Redis Connection Check (Fast, no hang)
# ===========================================
export REDIS_URL=redis://localhost:6379/0
echo "Checking Redis connection at localhost:6379 ..."

python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('127.0.0.1', 6379))
    s.close()
    print('✅ Redis is reachable at 127.0.0.1:6379')
except:
    print('❌ Redis is NOT reachable.')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo ""
    echo "Starting Redis via Docker..."
    if command -v docker &> /dev/null; then
        docker run -d --name my-redis -p 6379:6379 redis:7-alpine
        sleep 2
    else
        echo "❌ Docker is not installed. Please install Docker or Redis (valkey)."
        exit 1
    fi
fi

# ===========================================
# 2. Service Startup
# ===========================================
export PYTHONUNBUFFERED=1
export RQ_LOG_LEVEL=DEBUG
export REDIS_URL=redis://localhost:6379/0

echo "Starting services... (Press Ctrl+C to stop)"

# Start WebUI in background, logging to file & terminal
uv run gunicorn --bind 0.0.0.0:5055 --workers 1 --access-logfile - --log-level debug "apps.wheat_risk_webui:create_app()" > webui.log 2>&1 | tee webui.log &
WEBUI_PID=$!

# Start RQ Worker in background, logging to file & terminal
uv run python -m modules.jobs.worker > worker.log 2>&1 | tee worker.log &
WORKER_PID=$!

# ===========================================
# 3. Cleanup
# ===========================================
trap "echo 'Shutting down...'; kill $WEBUI_PID $WORKER_PID; docker stop my-redis &> /dev/null; docker rm my-redis &> /dev/null" EXIT

wait
