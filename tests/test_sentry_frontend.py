from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_next_sentry_logs_enabled_in_all_runtimes() -> None:
    client = FRONTEND / "instrumentation-client.ts"
    assert client.exists()

    for path in [
        client,
        FRONTEND / "sentry.server.config.ts",
        FRONTEND / "sentry.edge.config.ts",
    ]:
        source = path.read_text(encoding="utf-8")
        assert "enableLogs" in source
        assert "consoleLoggingIntegration" in source
        assert "beforeSend" in source
        assert "beforeSendLog" in source


def test_next15_instrumentation_exports_request_error_hook() -> None:
    instrumentation = (FRONTEND / "instrumentation.ts").read_text(encoding="utf-8")

    assert "onRequestError" in instrumentation
    assert "captureRequestError" in instrumentation


def test_server_sentry_uses_runtime_dsn_only() -> None:
    server = (FRONTEND / "sentry.server.config.ts").read_text(encoding="utf-8")

    assert "process.env.SENTRY_DSN" in server
    assert "process.env.NEXT_PUBLIC_SENTRY_DSN" not in server


def test_frontend_dockerfile_bakes_public_sentry_log_flags_only() -> None:
    dockerfile = (FRONTEND / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG NEXT_PUBLIC_SENTRY_ENABLE_LOGS=" in dockerfile
    assert "ARG NEXT_PUBLIC_SENTRY_ENVIRONMENT=" in dockerfile
    assert "ARG NEXT_PUBLIC_SENTRY_RELEASE=" in dockerfile
    assert "NEXT_PUBLIC_SENTRY_ENABLE_LOGS=$NEXT_PUBLIC_SENTRY_ENABLE_LOGS" in dockerfile
    assert "ARG SENTRY_DSN" not in dockerfile
