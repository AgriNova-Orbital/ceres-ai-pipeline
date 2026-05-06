from __future__ import annotations

import os
import re
import sys
import logging
from collections.abc import Mapping, Sequence
from typing import Any


REDACTED = "[Filtered]"
SENSITIVE_KEY_MARKERS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "x-api-key",
    "dsn",
    "credential",
    "client_secret",
    "refresh_token",
    "access_token",
    "clerk",
    "new_relic",
    "sentry_auth_token",
)
BEARER_PATTERN = re.compile(r"\b(authorization\s*:\s*bearer\s+)([^\s,;]+)", re.IGNORECASE)
COOKIE_PATTERN = re.compile(r"\b(cookie\s*:\s*)([^\n]+)", re.IGNORECASE)
ASSIGNMENT_PATTERN = re.compile(
    r"\b((?:access|refresh)[_-]?token|client[_-]?secret|api[_-]?key|"
    r"sentry[_-]?dsn|sentry[_-]?auth[_-]?token|new[_-]?relic[_-]?license[_-]?key|"
    r"clerk[_-]?secret[_-]?key|password|passwd|secret|token)\b(\s*[:=]\s*)([^\s,;&]+)",
    re.IGNORECASE,
)


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value < 0.0 or value > 1.0:
        return default
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _log_level_env(name: str, default: int | None) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().upper()
    if value in {"NONE", "OFF", "DISABLED"}:
        return None
    if value.isdigit():
        return int(value)
    level = getattr(logging, value, default)
    return level if isinstance(level, int) else default


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(marker in normalized for marker in SENSITIVE_KEY_MARKERS)


def _scrub_sensitive_string(value: str) -> str:
    value = BEARER_PATTERN.sub(r"\1" + REDACTED, value)
    value = COOKIE_PATTERN.sub(r"\1" + REDACTED, value)
    return ASSIGNMENT_PATTERN.sub(r"\1\2" + REDACTED, value)


def scrub_sentry_payload(payload: Any, hint: object | None = None) -> Any:
    if isinstance(payload, Mapping):
        return {
            key: REDACTED if _is_sensitive_key(key) else scrub_sentry_payload(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [scrub_sentry_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(scrub_sentry_payload(item) for item in payload)
    if isinstance(payload, str):
        return _scrub_sensitive_string(payload)
    return payload


def scrub_sentry_log(log: Any, hint: object | None = None) -> Any:
    return scrub_sentry_payload(log)


def configure_logging(service_name: str) -> None:
    level = _log_level_env("APP_LOG_LEVEL", _log_level_env("LOG_LEVEL", logging.INFO))
    if level is None:
        return
    logging.getLogger().setLevel(level)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=_bool_env("APP_LOG_FORCE", False),
    )
    rq_level = _log_level_env("RQ_LOG_LEVEL", level)
    if rq_level is not None:
        logging.getLogger("rq").setLevel(rq_level)
    logging.getLogger(__name__).debug("Configured logging for %s", service_name)


def init_sentry(service_name: str) -> bool:
    configure_logging(service_name)
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.rq import RqIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT")
        or os.environ.get("APP_ENV")
        or os.environ.get("FLASK_ENV")
        or "development",
        release=os.environ.get("SENTRY_RELEASE") or None,
        traces_sample_rate=_float_env("SENTRY_TRACES_SAMPLE_RATE", 0.0),
        profiles_sample_rate=_float_env("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
        send_default_pii=_bool_env("SENTRY_SEND_DEFAULT_PII", False),
        enable_logs=_bool_env("SENTRY_ENABLE_LOGS", True),
        before_send=scrub_sentry_payload,
        before_send_log=scrub_sentry_log,
        server_name=f"ceres-{service_name}",
        integrations=[
            FlaskIntegration(),
            RqIntegration(),
            LoggingIntegration(
                sentry_logs_level=_log_level_env("SENTRY_LOG_LEVEL", logging.INFO),
                level=_log_level_env("SENTRY_BREADCRUMB_LEVEL", logging.INFO),
                event_level=_log_level_env("SENTRY_EVENT_LEVEL", logging.ERROR),
            ),
        ],
    )
    return True


def build_new_relic_command(command: Sequence[str]) -> list[str]:
    if os.environ.get("NEW_RELIC_LICENSE_KEY") and os.environ.get(
        "NEW_RELIC_APP_NAME"
    ):
        return ["newrelic-admin", "run-program", *command]
    return list(command)


def main(argv: Sequence[str] | None = None) -> int:
    command = list(argv if argv is not None else sys.argv[1:])
    if not command:
        raise SystemExit("usage: python -m modules.observability <command> [args...]")
    wrapped = build_new_relic_command(command)
    os.execvp(wrapped[0], wrapped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
