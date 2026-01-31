from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RayHeadConfig:
    port: int = 6379
    dashboard_host: str = "0.0.0.0"


@dataclass(frozen=True)
class RayWorkerConfig:
    head_address: str
    num_gpus: int = 1


def python_version_tuple() -> tuple[int, int, int]:
    v = sys.version_info
    return (v.major, v.minor, v.micro)


def is_ray_supported_python() -> bool:
    """Return True if current Python is likely supported by Ray.

    Ray and PyTorch typically lag the newest CPython releases.
    Practically, Python 3.11-3.12 is the safe zone for most GPU stacks.
    """

    major, minor, _ = python_version_tuple()
    return major == 3 and minor in (11, 12)


def build_ray_head_command(cfg: RayHeadConfig) -> List[str]:
    if cfg.port <= 0 or cfg.port > 65535:
        raise ValueError("port must be in 1..65535")
    if not cfg.dashboard_host:
        raise ValueError("dashboard_host must be non-empty")

    return [
        "ray",
        "start",
        "--head",
        f"--port={cfg.port}",
        f"--dashboard-host={cfg.dashboard_host}",
        "--node-ip-address=192.168.2.2",
    ]


def build_ray_worker_command(cfg: RayWorkerConfig) -> List[str]:
    if not cfg.head_address:
        raise ValueError("head_address must be non-empty")
    if cfg.num_gpus <= 0:
        raise ValueError("num_gpus must be a positive int")

    return [
        "ray",
        "start",
        f"--address={cfg.head_address}",
        f"--num-gpus={cfg.num_gpus}",
    ]
