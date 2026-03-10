#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _import_ray():
    try:
        import ray  # type: ignore

        return ray
    except ImportError as e:
        raise SystemExit(
            "Ray is required. Install with `UV_PYTHON=3.12 uv sync --dev --extra distributed`."
        ) from e


def _load_hosts(path: Path) -> list[str]:
    hosts = [
        h.strip()
        for h in path.read_text().splitlines()
        if h.strip() and not h.strip().startswith("#")
    ]
    if not hosts:
        raise SystemExit(f"hosts file is empty: {path}")
    return hosts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Run a command once per specified Ray node (by NodeManagerAddress). "
            "Useful for git pull / uv sync fanout."
        )
    )
    p.add_argument(
        "--hosts", type=Path, required=True, help="hosts.txt (one node IP per line)"
    )
    p.add_argument(
        "--repo-dir", type=Path, required=True, help="Repo directory on each node"
    )
    p.add_argument(
        "--windows-repo-dir",
        type=str,
        default=None,
        help=(
            "Optional repo directory for Windows nodes. Supports env vars like %USERPROFILE%. "
            "Example: %USERPROFILE%\\Desktop\\ceres-ai-pipeline"
        ),
    )
    p.add_argument(
        "--posix",
        default="git pull",
        help="Command to run on Linux/macOS nodes (default: git pull)",
    )
    p.add_argument(
        "--windows",
        default="git pull",
        help="Command to run on Windows nodes (default: git pull)",
    )
    p.add_argument("--parallel", type=int, default=8)
    args = p.parse_args(argv)

    if args.parallel <= 0:
        raise SystemExit("--parallel must be > 0")
    repo_dir = args.repo_dir
    win_repo_dir = args.windows_repo_dir or str(args.repo_dir)

    ray = _import_ray()
    ray.init(address="auto")

    from modules.wheat_risk.fanout import (
        build_posix_bash_command,
        build_windows_cmd_command,
    )

    @ray.remote
    def run_on_node(
        posix_cmd: str,
        windows_cmd: str,
        posix_repo_dir_str: str,
        windows_repo_dir_str: str,
    ) -> dict[str, object]:
        import platform

        is_windows = platform.system().lower().startswith("win")

        repo = Path(windows_repo_dir_str) if is_windows else Path(posix_repo_dir_str)
        pcmd = (
            build_windows_cmd_command(repo_dir=repo, cmd=windows_cmd)
            if is_windows
            else build_posix_bash_command(repo_dir=repo, cmd=posix_cmd)
        )

        p = subprocess.run(pcmd.argv, check=False, text=True, capture_output=True)
        return {
            "node_ip": ray.util.get_node_ip_address(),
            "platform": platform.system(),
            "code": p.returncode,
            "stdout": (p.stdout or "").strip(),
            "stderr": (p.stderr or "").strip(),
        }

    hosts = _load_hosts(args.hosts)

    # Submit in chunks to avoid overwhelming the head.
    results: list[dict[str, object]] = []
    for i in range(0, len(hosts), args.parallel):
        chunk = hosts[i : i + args.parallel]
        refs = []
        for ip in chunk:
            refs.append(
                run_on_node.options(resources={f"node:{ip}": 0.001}).remote(
                    args.posix, args.windows, str(repo_dir), win_repo_dir
                )
            )
        results.extend(ray.get(refs))

    failures = 0
    for r in results:
        node_ip = r.get("node_ip")
        raw_code = r.get("code")
        code = int(raw_code) if isinstance(raw_code, int) else 0
        plat = r.get("platform")
        print(f"\n=== {node_ip} ({plat}) code={code} ===")
        out = str(r.get("stdout") or "")
        err = str(r.get("stderr") or "")
        if out:
            print(out)
        if err:
            print(err)
        if code != 0:
            failures += 1

    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
