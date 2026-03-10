#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ $# -ge 1 ]]; then
  export GOOGLE_OAUTH_CLIENT_SECRET_FILE="$1"
fi

if [[ -z "${GOOGLE_OAUTH_CLIENT_SECRET_FILE:-}" ]]; then
  echo "Usage: ./start_services_oauth.sh /absolute/path/to/client_secret_xxx.json"
  echo "Or export GOOGLE_OAUTH_CLIENT_SECRET_FILE first."
  exit 1
fi

if [[ ! -f "$GOOGLE_OAUTH_CLIENT_SECRET_FILE" ]]; then
  echo "Client secret file not found: $GOOGLE_OAUTH_CLIENT_SECRET_FILE"
  exit 1
fi

export USE_FAKEREDIS=1
export FLASK_ENV=development

echo "Starting WebUI with User-level OAuth + FakeRedis..."
echo "Client secret: $GOOGLE_OAUTH_CLIENT_SECRET_FILE"
echo "Open: http://127.0.0.1:5055"
echo "Press Ctrl+C to stop."

uv run gunicorn --bind 0.0.0.0:5055 --workers 1 "apps.wheat_risk_webui:create_app()"
