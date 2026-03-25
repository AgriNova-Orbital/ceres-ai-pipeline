#!/bin/bash
set -euo pipefail

VERBOSE=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: ./start_local_dev.sh [--verbose] [--dry-run]

Options:
  --verbose   Print commands and extra diagnostics.
  --dry-run   Print the commands that would run, but do not start services.
  --help      Show this help message.

Environment:
  USE_FAKEREDIS=1   Skip Redis auto-start and let the app/worker use fakeredis.
  REDIS_URL         Override Redis connection URL (default: redis://localhost:6379/0)
EOF
}

for arg in "$@"; do
  case "$arg" in
    --verbose)
      VERBOSE=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$VERBOSE" == "1" ]]; then
  echo "Verbose mode enabled"
  set -x
fi

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run]'
    for arg in "$@"; do
      printf ' %s' "$arg"
    done
    printf '\n'
  else
    "$@"
  fi
}

# ===========================================
# Environment Setup
# ===========================================
export PYTHONUNBUFFERED=1
export RQ_LOG_LEVEL=DEBUG
export REDIS_URL=redis://localhost:6379/0
export WEBUI_SECRET_KEY="${WEBUI_SECRET_KEY:-local-dev-secret-$(date +%s)}"

cleanup() {
  if [[ "$DRY_RUN" == "1" ]]; then
    return
  fi

  if [[ -n "${WORKER_PID:-}" ]]; then
    kill "$WORKER_PID" 2>/dev/null || true
  fi

  if [[ -n "${STARTED_DOCKER_REDIS:-}" ]] && [[ "$STARTED_DOCKER_REDIS" == "1" ]]; then
    if command -v docker &>/dev/null && docker ps -q -f name=my-redis >/dev/null 2>&1; then
      docker stop my-redis >/dev/null 2>&1 || true
      docker rm my-redis >/dev/null 2>&1 || true
    fi
  fi
}

trap cleanup EXIT

STARTED_DOCKER_REDIS=0

if [[ "${USE_FAKEREDIS:-0}" == "1" ]]; then
  echo "USE_FAKEREDIS=1 detected; skipping Redis auto-start."
else
  if command -v redis-server &>/dev/null; then
    echo "Redis is already installed. Ensure it is running before continuing."
  else
    echo "No local Redis found. Attempting to start via Docker..."
    if command -v docker &>/dev/null; then
      if [[ -z "$(docker ps -q -f name=my-redis)" ]]; then
        if [[ -n "$(docker ps -aq -f status=exited -f name=my-redis)" ]]; then
          run_cmd docker rm my-redis
        fi
        echo "Starting Redis container..."
        run_cmd docker run -d --name my-redis -p 6379:6379 redis:7-alpine
        STARTED_DOCKER_REDIS=1
      else
        echo "Redis container is already running."
      fi
    else
      echo "Warning: Neither local Redis nor Docker found."
      echo "Set USE_FAKEREDIS=1 to continue in local test mode."
      if [[ "$DRY_RUN" != "1" ]]; then
        exit 1
      fi
    fi
  fi
fi

export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

echo "Starting WebUI (Gunicorn, 1 worker) and RQ Worker..."

WORKER_CMD=(uv run python -m modules.jobs.worker)
GUNICORN_CMD=(uv run gunicorn --bind 0.0.0.0:5055 --workers 1 --access-logfile - --error-logfile -)

if [[ "$VERBOSE" == "1" ]]; then
  echo "Worker logs will stream to stdout"
  GUNICORN_CMD+=(--log-level debug)
fi

GUNICORN_CMD+=("apps.wheat_risk_webui:create_app()")

if [[ "$DRY_RUN" == "1" ]]; then
  run_cmd "${WORKER_CMD[@]}"
  run_cmd "${GUNICORN_CMD[@]}"
  exit 0
fi

if [[ "$VERBOSE" == "1" ]]; then
  "${WORKER_CMD[@]}" 2>&1 | tee -a rq_worker.log &
else
  "${WORKER_CMD[@]}" > rq_worker.log 2>&1 &
fi
WORKER_PID=$!

exec "${GUNICORN_CMD[@]}"
