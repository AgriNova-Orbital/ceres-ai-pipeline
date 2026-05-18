from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / "deploy" / "lab" / "portainer.env"
DEFAULT_STACK_ENV_FILE = ROOT / "deploy" / "lab" / "stack.env"
DEFAULT_STACK_FILE = ROOT / "deploy" / "lab" / "docker-compose.portainer.yml"

STACK_ENV_KEYS = (
    "APP_VERSION",
    "CERES_DATA_ROOT",
    "CERES_API_HOST_BIND",
    "CERES_FRONTEND_HOST_BIND",
    "CERES_API_IMAGE",
    "CERES_FRONTEND_IMAGE",
    "WEBUI_SECRET_KEY",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
    "CLERK_SECRET_KEY",
    "CLERK_JWT_ISSUER",
    "CLERK_JWT_AUDIENCE",
    "CLERK_JWKS_URL",
    "CLERK_JWKS_CACHE_TTL_SECONDS",
    "SENTRY_DSN",
    "NEXT_PUBLIC_SENTRY_DSN",
    "SENTRY_ENVIRONMENT",
    "SENTRY_RELEASE",
    "SENTRY_TRACES_SAMPLE_RATE",
    "SENTRY_PROFILES_SAMPLE_RATE",
    "SENTRY_SEND_DEFAULT_PII",
    "SENTRY_ENABLE_LOGS",
    "SENTRY_LOG_LEVEL",
    "SENTRY_BREADCRUMB_LEVEL",
    "SENTRY_EVENT_LEVEL",
    "APP_LOG_LEVEL",
    "NEXT_PUBLIC_SENTRY_ENABLE_LOGS",
    "NEXT_PUBLIC_SENTRY_ENVIRONMENT",
    "NEXT_PUBLIC_SENTRY_RELEASE",
    "NEW_RELIC_LICENSE_KEY",
    "NEW_RELIC_APP_NAME",
    "NEW_RELIC_WORKER_APP_NAME",
    "NEW_RELIC_LOG",
    "NEW_RELIC_DISTRIBUTED_TRACING_ENABLED",
)

REQUIRED_STACK_ENV_KEYS = (
    "WEBUI_SECRET_KEY",
    "CLERK_JWT_ISSUER",
    "CLERK_JWT_AUDIENCE",
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise ValueError(f"Env file does not exist: {path}")

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid env line {line_number} in {path}: expected KEY=VALUE")

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid env line {line_number} in {path}: empty key")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value

    return values


def require(config: dict[str, str], key: str) -> str:
    value = config.get(key, "")
    if value == "":
        raise ValueError(f"Missing required value: {key}")
    return value


def validate_immutable_image(image: str, *, label: str) -> None:
    if "@sha256:" in image:
        return
    _, separator, tag = image.rpartition(":")
    if not separator or not tag:
        raise ValueError(f"{label} image must include an explicit immutable tag")
    if tag == "latest":
        raise ValueError(f"{label} image uses latest; deploy an immutable tag instead")


def render_stack(stack_file: Path, api_image: str, frontend_image: str) -> str:
    content = stack_file.read_text(encoding="utf-8")
    return content.replace("${CERES_API_IMAGE}", api_image).replace(
        "${CERES_FRONTEND_IMAGE}", frontend_image
    )


def stack_env(config: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"name": key, "value": config[key]}
        for key in STACK_ENV_KEYS
        if key in config and config[key] != ""
    ]


def is_sensitive_name(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in ("TOKEN", "SECRET", "PASSWORD", "LICENSE_KEY"))


def redacted_payload(payload: dict[str, object]) -> dict[str, object]:
    safe_payload = copy.deepcopy(payload)
    headers = safe_payload.get("headers")
    if isinstance(headers, dict) and "X-API-Key" in headers:
        headers["X-API-Key"] = "<redacted>"

    body = safe_payload.get("body")
    if isinstance(body, dict):
        env = body.get("Env")
        if isinstance(env, list):
            for item in env:
                if isinstance(item, dict) and is_sensitive_name(str(item.get("name", ""))):
                    item["value"] = "<redacted>"

    return safe_payload


def build_payload(
    config: dict[str, str],
    *,
    target: str,
    api_image: str,
    frontend_image: str,
    stack_file: Path,
) -> dict[str, object]:
    validate_immutable_image(api_image, label="API")
    validate_immutable_image(frontend_image, label="Frontend")

    for key in REQUIRED_STACK_ENV_KEYS:
        require(config, key)

    portainer_url = require(config, "PORTAINER_URL").rstrip("/")
    token = require(config, "PORTAINER_API_TOKEN")
    endpoint_id = require(config, "PORTAINER_ENDPOINT_ID")
    stack_id = require(config, f"PORTAINER_{target.upper()}_STACK_ID")

    stack_config = dict(config)
    stack_config["CERES_API_IMAGE"] = api_image
    stack_config["CERES_FRONTEND_IMAGE"] = frontend_image

    return {
        "method": "PUT",
        "url": f"{portainer_url}/api/stacks/{stack_id}?endpointId={endpoint_id}",
        "headers": {
            "Content-Type": "application/json",
            "X-API-Key": token,
        },
        "body": {
            "StackFileContent": render_stack(stack_file, api_image, frontend_image),
            "Env": stack_env(stack_config),
            "Prune": True,
            "PullImage": True,
        },
    }


def send_payload(payload: dict[str, object], *, timeout: float) -> None:
    body = payload["body"]
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        str(payload["url"]),
        data=data,
        method=str(payload["method"]),
        headers=payload["headers"],  # type: ignore[arg-type]
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        sys.stdout.write(f"Portainer update accepted: HTTP {response.status}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deploy a Ceres lab stack through the Portainer API.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--stack-env-file", type=Path, default=DEFAULT_STACK_ENV_FILE)
    parser.add_argument("--stack-file", type=Path, default=DEFAULT_STACK_FILE)
    parser.add_argument("--target", choices=("staging", "pilot"), required=True)
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--frontend-image", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approve-pilot", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.target == "pilot" and not args.approve_pilot:
            raise ValueError("Pilot deployments require --approve-pilot after manual approval")

        config = parse_env_file(args.env_file)
        if args.stack_env_file.exists():
            config.update(parse_env_file(args.stack_env_file))
        payload = build_payload(
            config,
            target=args.target,
            api_image=args.api_image,
            frontend_image=args.frontend_image,
            stack_file=args.stack_file,
        )

        if args.dry_run:
            print(json.dumps(redacted_payload(payload), indent=2, sort_keys=True))
            return 0

        send_payload(payload, timeout=args.timeout)
        return 0
    except (OSError, ValueError, urllib.error.URLError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
