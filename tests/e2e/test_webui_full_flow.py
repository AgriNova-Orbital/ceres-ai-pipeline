"""End-to-end test: Setup + Login flow with Brave browser.

Usage:
    WEBUI_SECRET_KEY=test-secret-key uv run pytest tests/e2e/test_webui_full_flow.py -v -s
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

pytest.importorskip("selenium", reason="selenium not installed")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

BRAVE_BIN = "/usr/sbin/brave"
BASE_URL = "http://127.0.0.1:5055"


@pytest.fixture(scope="module")
def driver():
    opts = Options()
    opts.binary_location = BRAVE_BIN
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    d = webdriver.Chrome(options=opts)
    d.implicitly_wait(5)
    yield d
    d.quit()


# ── Setup Flow ──────────────────────────────────────────────


def test_01_setup_step1(driver):
    driver.get(f"{BASE_URL}/setup")
    body = driver.find_element(By.TAG_NAME, "body").text
    assert "App DB" in body
    print(f"\n[1] Step 1 OK → {driver.current_url}")


def test_02_setup_step2(driver):
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1)
    assert "OAuth Configuration" in driver.find_element(By.TAG_NAME, "body").text
    print(f"[2] Step 2 OK → {driver.current_url}")


def test_03_setup_submit_and_reach_step3(driver, tmp_path: Path):
    secret_file = tmp_path / "client_secret.json"
    secret_file.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "test-client-id.apps.googleusercontent.com",
                    "client_secret": "test-secret",
                    "redirect_uris": [f"{BASE_URL}/auth/callback"],
                }
            }
        ),
        encoding="utf-8",
    )

    driver.find_element(By.NAME, "redirect_base_url").send_keys(BASE_URL)
    driver.find_element(By.NAME, "oauth_client_secret_upload").send_keys(
        str(secret_file)
    )
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    for _ in range(20):
        if "step=3" in driver.current_url:
            break
        time.sleep(0.5)

    assert "step=3" in driver.current_url, f"Never reached step 3: {driver.current_url}"
    page = driver.page_source
    assert "Initialization" in page
    print(f"[3] Step 3 OK → {driver.current_url}")


# ── Post-Setup Flow (each test starts fresh to avoid cookie/session issues) ──


def test_04_dashboard_no_setup_loop(driver):
    """After setup, going to / should NOT redirect back to /setup."""
    driver.get(BASE_URL)
    time.sleep(1)
    url = driver.current_url
    body = driver.find_element(By.TAG_NAME, "body").text
    print(f"[4] GET / → {url}")
    print(f"    Body: {body[:120]}")
    assert "/setup" not in url, f"Bug: redirected to setup! URL={url}"
    assert "App DB" not in body, f"Bug: showing setup page!"


def test_05_login_redirects_to_google(driver):
    """/login should redirect to Google OAuth (not /setup)."""
    driver.get(f"{BASE_URL}/login")
    time.sleep(2)
    url = driver.current_url
    body = driver.find_element(By.TAG_NAME, "body").text
    print(f"[5] Login → {url}")
    print(f"    Body: {body[:120]}")

    assert "/setup" not in url, f"Bug: /login redirected to setup!"
    assert "accounts.google.com" in url, f"Expected Google redirect, got: {url}"
    # The test client_id doesn't exist in Google, so we expect invalid_client
    # But the important thing is: it went to Google, NOT back to setup
    print("    → Correctly redirected to Google OAuth")
