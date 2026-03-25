from __future__ import annotations

import os
import shutil
from typing import Any


def resolve_chrome_binaries() -> dict[str, str]:
    chrome = (
        os.environ.get("CHROME_BIN")
        or shutil.which("google-chrome")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
    )
    chromedriver = os.environ.get("CHROMEDRIVER_BIN") or shutil.which("chromedriver")
    if not chrome or not chromedriver:
        raise FileNotFoundError(
            f"Chrome binary: {chrome or 'NOT FOUND'}, "
            f"ChromeDriver: {chromedriver or 'NOT FOUND'}"
        )
    return {"chrome": chrome, "chromedriver": chromedriver}
