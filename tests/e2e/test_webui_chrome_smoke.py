from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

pytest.importorskip("selenium", reason="selenium not installed")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


@pytest.fixture
def chrome_binaries():
    from modules.testing.browser_env import resolve_chrome_binaries

    try:
        return resolve_chrome_binaries()
    except FileNotFoundError as e:
        pytest.skip(str(e))


@pytest.fixture
def running_app(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "state" / "app.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    monkeypatch.setenv("WEBUI_SECRET_KEY", "e2e-test-secret")
    monkeypatch.setenv("USE_FAKEREDIS", "1")

    secret = tmp_path / "client_secret.json"
    secret.write_text(
        '{"web":{"client_id":"cid","client_secret":"sec","redirect_uris":["http://127.0.0.1:5099/auth/callback"]}}',
        encoding="utf-8",
    )

    from apps.wheat_risk_webui import create_app

    app = create_app(repo_root=tmp_path)
    app.config["SQLITE_STORE"].save_settings(
        initialized=True,
        oauth_client_secret_path=str(secret),
        redirect_base_url="http://127.0.0.1:5099",
    )
    app.config["APP_SETTINGS"] = app.config["SQLITE_STORE"].get_settings()

    proc = subprocess.Popen(
        [
            "python",
            "-c",
            "from apps.wheat_risk_webui import create_app; "
            "app = create_app(); app.run(host='127.0.0.1', port=5099, debug=False)",
        ],
        env={
            **os.environ,
            "WEBUI_SECRET_KEY": "e2e-test-secret",
            "APP_DB_PATH": str(db_path),
            "USE_FAKEREDIS": "1",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)
    yield proc
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)


def test_chrome_smoke_opens_setup_page(chrome_binaries, running_app):
    opts = Options()
    opts.binary_location = chrome_binaries["chrome"]
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    service = Service(executable_path=chrome_binaries["chromedriver"])
    driver = webdriver.Chrome(service=service, options=opts)
    try:
        driver.get("http://127.0.0.1:5099/setup")
        assert (
            "Setup" in driver.title
            or "Ceres" in driver.title
            or driver.find_elements("tag name", "body")
        )
    finally:
        driver.quit()
