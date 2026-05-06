from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_build_route_has_tracked_page() -> None:
    build_page = ROOT / "frontend" / "app" / "build" / "page.tsx"

    assert build_page.exists()
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "frontend/app/build/page.tsx"],
        cwd=ROOT,
        check=False,
    )
    assert ignored.returncode != 0


def test_dashboard_links_only_to_existing_app_pages() -> None:
    dashboard = ROOT / "frontend" / "app" / "dashboard" / "page.tsx"
    text = dashboard.read_text(encoding="utf-8")

    for href in sorted(set(part.split('"', 1)[0] for part in text.split('href: "')[1:])):
        if href.startswith("/") and href not in {"/privacy", "/terms"}:
            assert (ROOT / "frontend" / "app" / href.strip("/") / "page.tsx").exists(), href


def test_job_submitting_panels_render_job_detail_card() -> None:
    for rel in [
        "frontend/app/build/page.tsx",
        "frontend/app/downloader/page.tsx",
        "frontend/app/evaluation/page.tsx",
        "frontend/app/inventory/page.tsx",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "JobDetailCard" in text, rel
