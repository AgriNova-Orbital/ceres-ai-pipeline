#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Serve dataset archives over HTTP for Ray workers to download. "
            "This binds to 0.0.0.0 by default."
        )
    )
    p.add_argument(
        "--root",
        type=Path,
        default=Path("datasets"),
        help="Directory to serve (default: ./datasets)",
    )
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--bind", default="0.0.0.0")
    args = p.parse_args(argv)

    if args.port <= 0 or args.port > 65535:
        raise SystemExit("--port must be in 1..65535")
    if not args.bind:
        raise SystemExit("--bind must be non-empty")

    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)

    from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

    server = ThreadingHTTPServer((args.bind, args.port), SimpleHTTPRequestHandler)
    print(f"Serving {root} on http://{args.bind}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
