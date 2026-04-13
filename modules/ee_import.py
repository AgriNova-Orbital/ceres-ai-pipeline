from __future__ import annotations

from typing import Any


def require_ee(feature: str) -> Any:
    """Import the Earth Engine module with a friendly error.

    This keeps tests EE-free and avoids raw ImportError tracebacks in CLIs.
    """

    try:
        import ee  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Google Earth Engine Python API (earthengine-api) is required for "
            f"{feature}. Install it and authenticate:\n"
            "  uv add earthengine-api\n"
            "  earthengine authenticate"
        ) from e

    return ee
