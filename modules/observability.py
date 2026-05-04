from __future__ import annotations

import os
import sys
from collections.abc import Sequence


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def init_sentry(service_name: str) -> bool:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    import sentry_sdk

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
        server_name=f"ceres-{service_name}",
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
