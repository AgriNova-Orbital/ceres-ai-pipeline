from __future__ import annotations

import subprocess
from pathlib import Path


def test_start_local_dev_exports_webui_secret_key(tmp_path: Path):
    script = Path(__file__).resolve().parent.parent / "start_local_dev.sh"
    assert script.exists(), "start_local_dev.sh not found"

    # Extract the WEBUI_SECRET_KEY export line and verify it sets a value
    content = script.read_text(encoding="utf-8")
    assert "WEBUI_SECRET_KEY" in content
    assert "export WEBUI_SECRET_KEY" in content
