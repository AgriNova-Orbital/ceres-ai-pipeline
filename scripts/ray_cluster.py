#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.wheat_risk.ray_cluster import (
    RayHeadConfig,
    RayWorkerConfig,
    build_ray_head_command,
    build_ray_worker_command,
    is_ray_supported_python,
    python_version_tuple,
)


def _print_cmd(cmd: list[str]) -> None:
    print(" ".join(shlex.quote(p) for p in cmd))


def _run_cmd(cmd: list[str]) -> int:
    try:
        proc = subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("ray not found. Install: uv sync --dev --extra distributed")
        return 127
    return int(proc.returncode)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Start a Ray head/worker (prints commands by default)."
    )
    parser.add_argument(
        "--exec",
        action="store_true",
        help="Execute the command instead of printing it.",
    )
    parser.add_argument(
        "--no-version-check",
        action="store_true",
        help="Skip the Python version compatibility warning.",
    )

    sub = parser.add_subparsers(dest="mode", required=True)

    head = sub.add_parser("head", help="Start Ray head.")
    head.add_argument("--port", type=int, default=6379)
    head.add_argument("--dashboard-host", default="0.0.0.0")

    worker = sub.add_parser("worker", help="Start Ray worker.")
    worker.add_argument(
        "--address",
        required=True,
        help="Ray head address, e.g. 100.x.y.z:6379 (Tailscale) or 192.168.x.y:6379 (LAN)",
    )
    worker.add_argument("--num-gpus", type=int, default=1)

    args = parser.parse_args(argv)

    if not args.no_version_check and not is_ray_supported_python():
        v = python_version_tuple()
        print(
            f"WARNING: Python {v[0]}.{v[1]}.{v[2]} may not be supported by Ray/Torch. "
            "Recommended: Python 3.11 or 3.12."
        )
        print("If you hit install errors, create a 3.12 venv: uv venv -p 3.12 --clear")

    if args.mode == "head":
        cmd = build_ray_head_command(
            RayHeadConfig(port=args.port, dashboard_host=args.dashboard_host)
        )
    else:
        cmd = build_ray_worker_command(
            RayWorkerConfig(head_address=args.address, num_gpus=args.num_gpus)
        )

    if args.exec:
        return _run_cmd(cmd)

    _print_cmd(cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
