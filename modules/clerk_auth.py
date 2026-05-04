from __future__ import annotations

import json
import os
import time
from urllib.request import urlopen


class ClerkAuthError(ValueError):
    pass


class ClerkVerificationUnavailable(RuntimeError):
    pass


_JWKS_CACHE: dict[str, tuple[float, dict]] = {}


def is_clerk_auth_enabled() -> bool:
    return bool(os.environ.get("CLERK_JWT_ISSUER", "").strip())


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise ClerkAuthError("Missing bearer token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ClerkAuthError("Missing bearer token")
    return token.strip()


def _jwks_url() -> str:
    explicit = os.environ.get("CLERK_JWKS_URL", "").strip()
    if explicit:
        return explicit
    issuer = os.environ.get("CLERK_JWT_ISSUER", "").strip().rstrip("/")
    if not issuer:
        raise ClerkAuthError("CLERK_JWT_ISSUER or CLERK_JWKS_URL is required")
    return f"{issuer}/.well-known/jwks.json"


def clear_jwks_cache() -> None:
    _JWKS_CACHE.clear()


def _jwks_cache_ttl_seconds() -> float:
    raw = os.environ.get("CLERK_JWKS_CACHE_TTL_SECONDS", "300").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 300.0


def _download_jwks(url: str) -> dict:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - URL is deployment config.
        return json.loads(response.read().decode("utf-8"))


def _fetch_jwks(url: str) -> dict:
    now = time.time()
    cached = _JWKS_CACHE.get(url)
    if cached is not None and cached[0] > now:
        return cached[1]
    try:
        jwks = _download_jwks(url)
    except Exception as e:
        raise ClerkVerificationUnavailable("Unable to fetch Clerk JWKS") from e
    _JWKS_CACHE[url] = (now + _jwks_cache_ttl_seconds(), jwks)
    return jwks


def _audience_matches(actual: object, expected: str) -> bool:
    if isinstance(actual, str):
        return actual == expected
    if isinstance(actual, list):
        return expected in actual
    return False


def verify_clerk_token(token: str) -> dict[str, object]:
    from authlib.jose import JsonWebKey, jwt

    issuer = os.environ.get("CLERK_JWT_ISSUER", "").strip().rstrip("/")
    if not issuer:
        raise ClerkAuthError("CLERK_JWT_ISSUER is required")

    try:
        jwks = JsonWebKey.import_key_set(_fetch_jwks(_jwks_url()))
    except ClerkVerificationUnavailable:
        raise
    except Exception as e:
        raise ClerkVerificationUnavailable("Unable to load Clerk JWKS") from e

    try:
        claims = jwt.decode(token, jwks)
        claims.validate()
    except Exception as e:
        raise ClerkAuthError("Invalid token") from e
    data = dict(claims)

    if str(data.get("iss", "")).rstrip("/") != issuer:
        raise ClerkAuthError("Invalid issuer")

    audience = os.environ.get("CLERK_JWT_AUDIENCE", "").strip()
    if audience and not _audience_matches(data.get("aud"), audience):
        raise ClerkAuthError("Invalid audience")

    if not data.get("sub"):
        raise ClerkAuthError("Missing subject")

    return data
